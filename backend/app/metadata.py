"""Validated, transactional catalog metadata helpers; callers own commits."""
from datetime import date
from typing import Annotated, Literal
import unicodedata
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, AfterValidator
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from .models import (Language, Country, Tag, MovieLanguage, MovieCountry, MovieTag,
    MovieMetadata, MovieAlternativeTitle, MovieCertification, MovieSoundtrack, MovieQuote,
    PersonMetadata, PersonAlternativeName, PersonNationality, MovieMetadataOverride, PersonMetadataOverride, utcnow)


def clean(value: str) -> str:
    if '\x00' in value:
        raise ValueError('NUL characters are not allowed')
    return value.strip()


def label(value: str, maximum=120) -> str:
    value = ' '.join(unicodedata.normalize('NFKC', clean(value)).split())
    if not value or len(value) > maximum or len(value.casefold()) > 480:
        raise ValueError(f'Expected a nonempty label of at most {maximum} characters')
    return value


def title_label(value: str) -> str:
    return label(value, 240)


def safe_url(value: str) -> str:
    value = clean(value)
    parsed = urlsplit(value)
    if (parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or any(c.isspace() or ord(c)<32 for c in value) or '\\' in value):
        raise ValueError('Expected an HTTP(S) URL without credentials')
    # Accessing port verifies malformed/out-of-range port numbers.
    _ = parsed.port
    return value


Label = Annotated[str, Field(min_length=1, max_length=120), AfterValidator(label)]
TitleLabel = Annotated[str, Field(min_length=1, max_length=240), AfterValidator(title_label)]
ShortText = Annotated[str, Field(max_length=240), AfterValidator(clean)]
ExternalURL = Annotated[str, Field(max_length=600), AfterValidator(safe_url)]
CreditRole = Literal['actor','director','writer','producer','composer','cinematographer','editor','other']


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class CertificationInput(StrictInput):
    country: Label
    rating: Annotated[str, Field(min_length=1,max_length=32), AfterValidator(clean)]


class SoundtrackInput(StrictInput):
    title: TitleLabel
    artist: ShortText = ''
    composer: ShortText = ''
    external_url: ExternalURL | None = None


class QuoteInput(StrictInput):
    quote: Annotated[str, Field(min_length=1,max_length=500), AfterValidator(clean)]
    speaker: ShortText = ''
    spoiler: bool = False
    source_url: ExternalURL | None = None


class MovieMetadataPatch(StrictInput):
    original_title: TitleLabel | None = None
    release_date: date | None = None
    release_status: Literal['released','upcoming','in_production','cancelled'] | None = None
    trailer_url: ExternalURL | None = None
    alternative_titles: list[TitleLabel] = Field(default_factory=list,max_length=50)
    original_language: Label | None = None
    spoken_languages: list[Label] = Field(default_factory=list,max_length=50)
    unspecified_languages: list[Label] = Field(default_factory=list,max_length=50)
    production_countries: list[Label] = Field(default_factory=list,max_length=50)
    tags: list[Label] = Field(default_factory=list,max_length=100)
    certifications: list[CertificationInput] = Field(default_factory=list,max_length=100)
    soundtracks: list[SoundtrackInput] = Field(default_factory=list,max_length=200)
    quotes: list[QuoteInput] = Field(default_factory=list,max_length=100)


class PersonMetadataPatch(StrictInput):
    full_name: TitleLabel | None = None
    profile_url: ExternalURL | None = None
    birthday: date | None = None
    deathday: date | None = None
    birthplace: TitleLabel | None = None
    alternative_names: list[TitleLabel] = Field(default_factory=list,max_length=50)
    nationalities: list[Label] = Field(default_factory=list,max_length=50)


MOVIE_SCALARS = ('original_title','release_date','release_status','trailer_url')
PERSON_SCALARS = ('full_name','profile_url','birthday','deathday','birthplace')
MOVIE_EXTENSION_MODELS = (MovieLanguage, MovieCountry, MovieTag, MovieMetadata,
    MovieAlternativeTitle, MovieCertification, MovieSoundtrack, MovieQuote, MovieMetadataOverride)


def labels(values):
    result = {}
    for value in values:
        result.setdefault(value.casefold(), value)
    return result


def vocabulary(db, model, name):
    # Inputs validated by Pydantic or legacy normalization. Keep first display name.
    key = name.casefold()
    stmt = {'sqlite': sqlite_insert, 'postgresql': pg_insert}[db.get_bind().dialect.name](model)
    db.execute(stmt.values(key=key, name=name).on_conflict_do_nothing(index_elements=['key']))
    return db.scalar(select(model).where(model.key == key))


def rows(db, model, owner, identity, *order):
    return list(db.scalars(select(model).where(getattr(model, owner)==identity).order_by(*order)))


def replace(db, model, owner, identity, entries):
    db.execute(delete(model).where(getattr(model, owner)==identity))
    db.flush()
    db.add_all(model(**{owner: identity, **entry}) for entry in entries)
    db.flush()


def legacy_label(value):
    value = clean(value or '')
    if not value:
        return None
    try:
        return label(value)
    except ValueError:
        # Same preservation rule as the migration for unusual Unicode expansion.
        return ' '.join(value.split())


def sync_legacy_labels(db, movie, *, language_changed=True, country_changed=True):
    """Legacy admin/import write: a free-text value is one unspecified label."""
    if language_changed:
        name = legacy_label(movie.language)
        entries = [{'language_id': vocabulary(db, Language, name).id, 'kind':'unspecified'}] if name else []
        replace(db, MovieLanguage, 'movie_id', movie.id, entries)
        db.expire(movie, ['language_links'])
    if country_changed:
        name = legacy_label(movie.country)
        entries = [{'country_id': vocabulary(db, Country, name).id}] if name else []
        replace(db, MovieCountry, 'movie_id', movie.id, entries)
        db.expire(movie, ['country_links'])


def check_legacy_update(movie, language, country):
    # Old forms cannot express multiple countries or qualified languages. Do not
    # erase richer metadata simply because an old form submits its legacy fields.
    if language != movie.language and (len(movie.language_links)>1 or any(x.kind!='unspecified' for x in movie.language_links)):
        raise ValueError('Use structured metadata to change this film’s languages')
    if country != movie.country and len(movie.country_links)>1:
        raise ValueError('Use structured metadata to change this film’s production countries')


def language_summary(movie):
    linked = movie.language_links
    original = next((x.language.name for x in linked if x.kind=='original'), None)
    spoken = sorted((x.language.name for x in linked if x.kind=='spoken'),key=str.casefold)
    unknown = sorted((x.language.name for x in linked if x.kind=='unspecified'),key=str.casefold)
    if not linked and movie.language.strip():
        unknown = [movie.language.strip()]
    return {'original_language':original,'spoken_languages':spoken,'unspecified_languages':unknown}


def country_summary(movie):
    names = sorted((x.country.name for x in movie.country_links), key=str.casefold)
    return names or ([movie.country.strip()] if movie.country.strip() else [])


def movie_summary(movie):
    return {**language_summary(movie),'production_countries':country_summary(movie)}


def movie_metadata_out(db, movie):
    mid=movie.id
    ext=db.get(MovieMetadata,mid)
    return {'movie_id':mid, **{k:getattr(ext,k,None) for k in MOVIE_SCALARS}, **movie_summary(movie),
        'alternative_titles':[x.title for x in rows(db,MovieAlternativeTitle,'movie_id',mid,MovieAlternativeTitle.key)],
        'tags':sorted((x.tag.name for x in rows(db,MovieTag,'movie_id',mid,MovieTag.tag_id)), key=str.casefold),
        'certifications':sorted(({'country':x.country.name,'rating':x.rating} for x in rows(db,MovieCertification,'movie_id',mid,MovieCertification.country_id,MovieCertification.rating)),key=lambda x:(x['country'].casefold(),x['rating'])),
        'soundtracks':[{k:getattr(x,k) for k in ('title','artist','composer','external_url')} for x in rows(db,MovieSoundtrack,'movie_id',mid,MovieSoundtrack.position)],
        'quotes':[{k:getattr(x,k) for k in ('quote','speaker','spoiler','source_url')} for x in rows(db,MovieQuote,'movie_id',mid,MovieQuote.position)]}


def apply_movie_metadata(db, movie, patch: MovieMetadataPatch):
    """PATCH semantics: omitted fields stay unchanged; []/null explicitly clear."""
    changes=patch.model_dump(exclude_unset=True)
    mid=movie.id
    if any(k in changes for k in MOVIE_SCALARS):
        ext=db.get(MovieMetadata,mid) or MovieMetadata(movie_id=mid)
        db.add(ext)
        for k in MOVIE_SCALARS:
            if k in changes: setattr(ext,k,changes[k])
    if 'alternative_titles' in changes:
        replace(db,MovieAlternativeTitle,'movie_id',mid,[{'key':k,'title':v} for k,v in labels(patch.alternative_titles).items()])
    lang_fields=('original_language','spoken_languages','unspecified_languages')
    if any(k in changes for k in lang_fields):
        values=language_summary(movie)
        values.update({k:changes[k] for k in lang_fields if k in changes})
        originals=[values['original_language']] if values['original_language'] else []
        spoken=labels(values['spoken_languages'])
        classified=set(labels(originals)) | set(spoken)
        unknown={k:v for k,v in labels(values['unspecified_languages']).items() if k not in classified}
        entries=[{'language_id':vocabulary(db,Language,name).id,'kind':kind}
                 for kind,names in [('original',originals),('spoken',spoken.values()),('unspecified',unknown.values())] for name in names]
        replace(db,MovieLanguage,'movie_id',mid,entries)
        # The old 100-character field is a compatibility preview only. Prefer
        # a whole label; never cut a new label into a misleading partial name.
        candidates=[*originals,*sorted(spoken.values(),key=str.casefold),*sorted(unknown.values(),key=str.casefold)]
        movie.language=next((v for v in candidates if len(v)<=100),'')
        db.expire(movie,['language_links'])
    if 'production_countries' in changes:
        names=labels(patch.production_countries)
        replace(db,MovieCountry,'movie_id',mid,[{'country_id':vocabulary(db,Country,name).id} for name in names.values()])
        movie.country=next((v for v in sorted(names.values(),key=str.casefold) if len(v)<=100),'')
        db.expire(movie,['country_links'])
    if 'tags' in changes:
        replace(db,MovieTag,'movie_id',mid,[{'tag_id':vocabulary(db,Tag,name).id} for name in labels(patch.tags).values()])
    if 'certifications' in changes:
        entries={}
        for c in patch.certifications:
            cid=vocabulary(db,Country,c.country).id
            entries.setdefault((cid,c.rating.casefold()),{'country_id':cid,'rating':c.rating})
        replace(db,MovieCertification,'movie_id',mid,entries.values())
    for field,model in [('soundtracks',MovieSoundtrack),('quotes',MovieQuote)]:
        if field in changes:
            replace(db,model,'movie_id',mid,[dict(position=i,**entry) for i,entry in enumerate(changes[field])])
    db.flush()


def person_metadata_out(db,person):
    pid=person.id
    ext=db.get(PersonMetadata,pid)
    return {'person_id':pid,**{k:getattr(ext,k,None) for k in PERSON_SCALARS},
        'alternative_names':[x.name for x in rows(db,PersonAlternativeName,'person_id',pid,PersonAlternativeName.key)],
        'nationalities':sorted((x.country.name for x in rows(db,PersonNationality,'person_id',pid,PersonNationality.country_id)),key=str.casefold)}


def apply_person_metadata(db,person,patch:PersonMetadataPatch):
    changes=patch.model_dump(exclude_unset=True)
    pid=person.id
    if any(k in changes for k in PERSON_SCALARS):
        ext=db.get(PersonMetadata,pid) or PersonMetadata(person_id=pid)
        birthday=changes.get('birthday',ext.birthday)
        deathday=changes.get('deathday',ext.deathday)
        if birthday and deathday and deathday<birthday:
            raise ValueError('Death date cannot precede birth date')
        if any(d and d>date.today() for d in (birthday,deathday)):
            raise ValueError('Birth and death dates cannot be in the future')
        db.add(ext)
        for k in PERSON_SCALARS:
            if k in changes: setattr(ext,k,changes[k])
    if 'alternative_names' in changes:
        replace(db,PersonAlternativeName,'person_id',pid,[{'key':k,'name':v} for k,v in labels(patch.alternative_names).items()])
    if 'nationalities' in changes:
        replace(db,PersonNationality,'person_id',pid,[{'country_id':vocabulary(db,Country,name).id} for name in labels(patch.nationalities).values()])
    db.flush()



def record_overrides(db, model, owner, identity, fields):
    """Protect explicit manual values (even blank) from future enrichment."""
    insert = {'sqlite':sqlite_insert,'postgresql':pg_insert}[db.get_bind().dialect.name]
    for field in sorted(fields):
        stmt=insert(model).values(**{owner:identity},field=field,edited_at=utcnow())
        db.execute(stmt.on_conflict_do_update(index_elements=[owner,'field'],set_={'edited_at':stmt.excluded.edited_at}))
