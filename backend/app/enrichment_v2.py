"""Fill missing metadata from already-linked TMDB identities, without fuzzy matching."""
from dataclasses import dataclass
from datetime import date
import re
import time

from sqlalchemy import select, func
from pydantic import ValidationError

from .enrichment import (TMDBClient, ProviderError, Report, IMDB, IMAGE_PATH, ROLES,
    apply_details, record_field, valid_text)
from .metadata import (MovieMetadataPatch, PersonMetadataPatch, movie_metadata_out,
    person_metadata_out, apply_movie_metadata, apply_person_metadata, label, vocabulary)
from .models import (Movie, MovieSource, MovieCredit, MovieEnrichmentField, MovieMetadataOverride,
    Person, PersonSource, PersonEnrichmentField, PersonMetadataOverride, Language, Country)

ID = re.compile(r'[1-9][0-9]{0,15}\Z')
LANG = re.compile(r'[a-z]{2}\Z')
COUNTRY = re.compile(r'[A-Z]{2}\Z')
VIDEO = re.compile(r'[A-Za-z0-9_-]{11}\Z')
EXTRA_ROLES = {**ROLES, 'Original Music Composer':'composer', 'Director of Photography':'cinematographer', 'Editor':'editor'}
STATUS = {'Released':'released','Planned':'upcoming','In Production':'in_production',
          'Post Production':'in_production','Canceled':'cancelled'}


def objects(value):
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def section(details, name, key):
    value = details.get(name)
    return objects(value.get(key)) if isinstance(value, dict) else []


def unique_text(values, maximum, limit):
    out = {}
    for value in values:
        if valid_text(value, maximum):
            try:
                value = label(value, maximum)
            except ValueError:
                continue
            out.setdefault(value.casefold(), value)
    # Stable provider ordering; excessive lists are not silently truncated.
    return list(out.values()) if len(out) <= limit else []


def iso_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


class EnrichmentClient(TMDBClient):
    def __init__(self, token, *, transport=None, interval=.2):
        super().__init__(token, transport=transport)
        self.interval = interval
        self.last_request = None
        self.profile_base = ''
        self.languages = {}
        self.countries = {}

    def get(self, path, **params):
        if self.last_request is not None:
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        return super().get(path, **params)

    def configuration(self):
        images = self.get('configuration').get('images')
        if (not isinstance(images, dict) or images.get('secure_base_url') != 'https://image.tmdb.org/t/p/'
                or 'w500' not in (images.get('poster_sizes') or []) or 'w185' not in (images.get('profile_sizes') or [])):
            raise ProviderError('Unexpected TMDB image configuration')
        self.poster_base = images['secure_base_url'] + 'w500'
        self.profile_base = images['secure_base_url'] + 'w185'
        self.languages = self._vocabulary('languages', 'iso_639_1', LANG)
        self.countries = self._vocabulary('countries', 'iso_3166_1', COUNTRY)

    def _vocabulary(self, endpoint, key, pattern):
        mapping = {}
        for item in objects(self.get('configuration/'+endpoint, response_list=True)):
            code, name = item.get(key), item.get('english_name')
            if isinstance(code, str) and pattern.fullmatch(code) and valid_text(name, 120):
                try:
                    name = label(name)
                except ValueError:
                    continue
                if code in mapping and mapping[code] != name:
                    raise ProviderError('Conflicting TMDB classification configuration')
                mapping[code] = name
        if not mapping:
            raise ProviderError('Missing TMDB classification configuration')
        return mapping

    def linked_movie(self, external):
        return self.get('movie/'+external, language='en-US',
            append_to_response='credits,alternative_titles,release_dates,keywords,videos')

    def linked_person(self, external):
        return self.get('person/'+external, language='en-US')


@dataclass
class EnrichmentReport(Report):
    person_candidates: int = 0
    persons_matched: int = 0
    persons_skipped: int = 0
    person_fields_filled: int = 0
    protected_fields: int = 0
    unavailable_fields: int = 0
    classification_codes_added: int = 0
    unlinked_movies: int = 0
    last_movie_id: int | None = None


class ClassificationConflict(ValueError):
    pass


def resolve_code(db, model, code, mapping, report):
    """Reconcile exact normalized labels/codes only; don't merge vocabulary rows."""
    name = mapping.get(code) if isinstance(code, str) else None
    if not name:
        raise ClassificationConflict('unknown provider classification code')
    by_code = db.scalar(select(model).where(model.code == code))
    by_name = db.scalar(select(model).where(model.key == name.casefold()))
    if by_code and by_name and by_code.id != by_name.id:
        raise ClassificationConflict('code and label refer to different local rows')
    row = by_code or by_name or vocabulary(db, model, name)
    if row.code and row.code != code:
        raise ClassificationConflict('local label has a different code')
    if row.code is None:
        row.code = code
        db.flush()
        report.classification_codes_added += 1
    return row.name


def protected(db, entity, field, *, person=False):
    override, history = ((PersonMetadataOverride, PersonEnrichmentField) if person else
                         (MovieMetadataOverride, MovieEnrichmentField))
    return db.get(override, (entity.id, field)) is not None or db.get(history, (entity.id, field, 'tmdb')) is not None


def missing(db, entity, name, current, report, *, person=False):
    if current or protected(db, entity, name, person=person):
        report.protected_fields += 1
        return False
    return True


def apply_movie_field(db, movie, field, value, external, report):
    if not value:
        report.unavailable_fields += 1
        return False
    try:
        patch = MovieMetadataPatch.model_validate({field: value})
    except ValidationError:
        report.issues.append(f'movie {movie.id}: invalid {field}')
        return False
    legacy_language = movie.language
    apply_movie_metadata(db, movie, patch)
    if field in ('original_language','spoken_languages') and legacy_language.strip():
        movie.language = legacy_language
    record_field(db, movie, field, external)
    report.fields_filled += 1
    return True


def coded_movie_field(db, movie, field, codes, mapping, model, external, report, *, certification=False):
    if not codes:
        report.unavailable_fields += 1
        return
    before_codes = report.classification_codes_added
    try:
        with db.begin_nested():
            if certification:
                values = [{'country':resolve_code(db, model, code, mapping, report), 'rating':rating} for code,rating in codes]
                normalized = {(v['country'].casefold(),v['rating'].casefold()):v for v in values}
                value = list(normalized.values())
            else:
                values = [resolve_code(db, model, code, mapping, report) for code in codes]
                value = values[0] if field == 'original_language' else list(dict.fromkeys(values))
            if not apply_movie_field(db, movie, field, value, external, report):
                raise ClassificationConflict('invalid classification field')
    except ClassificationConflict as exc:
        report.classification_codes_added = before_codes
        report.issues.append(f'movie {movie.id}: {field}: {exc}')


def movie_fields(db, movie, details, provider, report):
    ext = str(details['id'])
    current = movie_metadata_out(db, movie)
    video = next((x['key'] for x in section(details, 'videos', 'results')
        if x.get('site') == 'YouTube' and x.get('type') == 'Trailer' and x.get('official') is True
        and isinstance(x.get('key'), str) and VIDEO.fullmatch(x['key'])), None)
    candidates = {
        'original_title':valid_text(details.get('original_title'),240),
        'release_date':iso_date(details.get('release_date')),
        'release_status':STATUS.get(details.get('status')) if isinstance(details.get('status'),str) else None,
        'trailer_url':'https://www.youtube.com/watch?v='+video if video else None,
        'alternative_titles':unique_text((x.get('title') for x in section(details,'alternative_titles','titles')),240,50),
        'tags':unique_text((x.get('name') for x in section(details,'keywords','keywords')),120,100),
    }
    for name, value in candidates.items():
        if missing(db,movie,name,current[name],report):
            apply_movie_field(db,movie,name,value,ext,report)
    # A manually changed unspecified classification (including an explicit clear)
    # protects it from the metadata helper's automatic removal of redundant labels.
    legacy = current['unspecified_languages']
    language_locked = protected(db,movie,'unspecified_languages')
    original = details.get('original_language')
    spoken = [x.get('iso_639_1') for x in objects(details.get('spoken_languages'))]
    # Reconcile legacy labels against the entire provider language set so an
    # exact spoken-language match need not wait for a second import to fill the
    # original language. Unknown or conflicting free-text labels stay untouched.
    known_names = set()
    for code in [original,*spoken]:
        if not isinstance(code,str) or code not in provider.languages:
            continue
        local = db.scalar(select(Language).where(Language.code==code))
        known_names.add((local.name if local else provider.languages[code]).casefold())
    compatible_legacy = not legacy or all(x.casefold() in known_names for x in legacy)
    for field,codes in [('original_language',[original] if original else []),('spoken_languages',spoken)]:
        if language_locked:
            report.protected_fields += 1
            continue
        if missing(db,movie,field,current[field],report):
            if not compatible_legacy:
                report.issues.append(f'movie {movie.id}: {field}: legacy language differs from provider classifications')
                continue
            coded_movie_field(db,movie,field,codes,provider.languages,Language,ext,report)
    if missing(db,movie,'production_countries',current['production_countries'],report):
        codes = [x.get('iso_3166_1') for x in objects(details.get('production_countries'))]
        coded_movie_field(db,movie,'production_countries',codes,provider.countries,Country,ext,report)
    if missing(db,movie,'certifications',current['certifications'],report):
        certs = []
        for country in section(details,'release_dates','results'):
            for entry in objects(country.get('release_dates')):
                rating = valid_text(entry.get('certification'),32)
                if rating:
                    certs.append((country.get('iso_3166_1'),rating))
        coded_movie_field(db,movie,'certifications',certs,provider.countries,Country,ext,report,certification=True)


def person_fields(db, person, details, provider, report):
    external = str(details['id'])
    current = {**person_metadata_out(db,person),'biography':person.biography}
    path = details.get('profile_path')
    candidates = {'biography':valid_text(details.get('biography'),10000),
        'profile_url':provider.profile_base+path if isinstance(path,str) and IMAGE_PATH.fullmatch(path) else None,
        'birthday':iso_date(details.get('birthday')),'deathday':iso_date(details.get('deathday')),
        'birthplace':valid_text(details.get('place_of_birth'),240),
        'alternative_names':unique_text(details.get('also_known_as') if isinstance(details.get('also_known_as'),list) else [],240,50)}
    for field, value in candidates.items():
        if not missing(db,person,field,current[field],report,person=True):
            continue
        if not value:
            report.unavailable_fields += 1
            continue
        try:
            if field == 'biography':
                person.biography = value
            else:
                # Validate before touching the extension object; invalid provider dates
                # cannot poison the transaction or overwrite a manual date.
                if field in ('birthday','deathday'):
                    birth = value if field=='birthday' else current['birthday']
                    death = value if field=='deathday' else current['deathday']
                    if value > date.today() or (birth and death and death<birth):
                        raise ValueError('inconsistent person dates')
                patch=PersonMetadataPatch.model_validate({field:value})
                apply_person_metadata(db,person,patch)
        except ValueError:
            report.issues.append(f'person {person.id}: invalid {field}')
            continue
        current[field]=value
        db.add(PersonEnrichmentField(person_id=person.id,field=field,source='tmdb',external_id=external))
        db.flush()
        report.person_fields_filled += 1


def enrich_linked(db, provider, *, limit=None, after_movie_id=0, cast_limit=12, dry_run=True, progress=None):
    """Caller owns transaction; use one importer and no concurrent catalog edits."""
    report = EnrichmentReport(dry_run=dry_run)
    # Python's sqlite3 legacy transaction mode can otherwise release a top-level
    # SAVEPOINT as a commit when no write has started the outer transaction yet.
    connection = db.connection()
    if connection.dialect.name == 'sqlite' and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql('BEGIN')
    stmt = select(MovieSource).where(MovieSource.source=='tmdb',MovieSource.movie_id>after_movie_id).order_by(MovieSource.movie_id)
    if limit is not None:
        stmt=stmt.limit(limit)
    targets=list(db.scalars(stmt))
    report.unlinked_movies=db.scalar(select(func.count()).select_from(Movie).where(~select(MovieSource.movie_id).where(MovieSource.movie_id==Movie.id,MovieSource.source=='tmdb').exists()))
    report.candidates=len(targets)
    if not targets:
        return report
    provider.configuration()
    people=set()
    for source in targets:
        mid, external = source.movie_id,source.external_id
        report.last_movie_id=mid
        movie=db.scalar(select(Movie).where(Movie.id==mid).with_for_update())
        imdb=db.scalar(select(MovieSource.external_id).where(MovieSource.movie_id==mid,MovieSource.source=='imdb'))
        if not movie or not ID.fullmatch(external) or not imdb or not IMDB.fullmatch(imdb):
            report.skipped+=1;report.issues.append(f'movie {mid}: missing or invalid linked identity');continue
        if progress: progress(f'Movie {mid} ({report.matched+report.skipped+1}/{report.candidates})')
        try:
            details=provider.linked_movie(external)
        except ProviderError as exc:
            if getattr(exc,'status_code',None)!=404: raise
            report.skipped+=1;report.issues.append(f'movie {mid}: provider identity not found');continue
        if type(details.get('id')) is not int or str(details['id'])!=external or details.get('imdb_id')!=imdb:
            report.skipped+=1;report.issues.append(f'movie {mid}: conflicting provider identity');continue
        release=iso_date(details.get('release_date'))
        if release and abs(release.year-movie.year)>1:
            report.skipped+=1;report.issues.append(f'movie {mid}: release year mismatch');continue
        apply_details(db,movie,details,provider,report,cast_limit,roles=EXTRA_ROLES)
        movie_fields(db,movie,details,provider,report)
        people.update(db.scalars(select(MovieCredit.person_id).where(MovieCredit.movie_id==mid)))
        report.matched+=1
    report.person_candidates=len(people)
    for i,pid in enumerate(sorted(people),1):
        external=db.scalar(select(PersonSource.external_id).where(PersonSource.person_id==pid,PersonSource.source=='tmdb'))
        person=db.scalar(select(Person).where(Person.id==pid).with_for_update())
        if not person or not external or not ID.fullmatch(external):
            report.persons_skipped+=1;report.issues.append(f'person {pid}: missing or invalid linked identity');continue
        if progress and (i==1 or i%25==0 or i==len(people)): progress(f'Person {i}/{len(people)}')
        try:
            details=provider.linked_person(external)
        except ProviderError as exc:
            if getattr(exc,'status_code',None)!=404: raise
            report.persons_skipped+=1;report.issues.append(f'person {pid}: provider identity not found');continue
        if type(details.get('id')) is not int or str(details['id'])!=external:
            report.persons_skipped+=1;report.issues.append(f'person {pid}: conflicting provider identity');continue
        person_fields(db,person,details,provider,report)
        report.persons_matched+=1
    return report
