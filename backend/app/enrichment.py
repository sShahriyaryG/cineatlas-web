"""Fill missing movie metadata using verified external identities, never title guesses."""
from __future__ import annotations

import csv
import re
import time
from dataclasses import dataclass, field
from typing import TextIO

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .ingestion import QID, clean
from .models import Movie, MovieSource, Person, PersonSource, MovieCredit, MovieEnrichmentField

IMDB = re.compile(r'tt[0-9]{7,12}\Z')
IMAGE_PATH = re.compile(r'/[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)\Z', re.I)
ROLES = {'Director': 'director', 'Writer': 'writer', 'Screenplay': 'writer',
         'Story': 'writer', 'Producer': 'producer'}


class ProviderError(Exception):
    """Safe diagnostic without credentials or raw response body."""


class TMDBClient:
    def __init__(self, token: str, *, transport=None):
        if not token.strip() or any(c.isspace() for c in token.strip()):
            raise ValueError('Provide the TMDB API Read Access Token')
        self.client = httpx.Client(base_url='https://api.themoviedb.org/3/',
                                   headers={'Authorization': 'Bearer ' + token.strip(), 'Accept': 'application/json'},
                                   timeout=45, follow_redirects=False, transport=transport)
        self.poster_base = ''

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()

    def get(self, path, **params):
        for attempt in range(3):
            try:
                response = self.client.get(path, params=params)
            except httpx.RequestError:
                if attempt == 2:
                    raise ProviderError('TMDB network request failed; retry later') from None
                time.sleep(2 ** attempt)
                continue
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                retry = response.headers.get('Retry-After', '')
                if retry.isdigit() and int(retry) > 60:
                    raise ProviderError('TMDB requested a longer retry interval; try later')
                time.sleep(max(1, int(retry)) if retry.isdigit() else 2 ** attempt)
                continue
            if response.status_code != 200:
                raise ProviderError(f'TMDB HTTP {response.status_code}; check access or try later')
            try:
                result = response.json()
            except ValueError:
                raise ProviderError('TMDB returned invalid JSON') from None
            if not isinstance(result, dict) or result.get('success') is False:
                raise ProviderError('TMDB returned an invalid response object')
            return result
        raise ProviderError('TMDB request failed')

    def configuration(self):
        images = self.get('configuration').get('images')
        if not isinstance(images, dict) or images.get('secure_base_url') != 'https://image.tmdb.org/t/p/' or 'w500' not in (images.get('poster_sizes') or []):
            raise ProviderError('Unexpected TMDB image configuration')
        self.poster_base = images['secure_base_url'] + 'w500'

    def movie(self, imdb_id):
        results = self.get(f'find/{imdb_id}', external_source='imdb_id', language='en-US').get('movie_results')
        if not isinstance(results, list):
            raise ProviderError('TMDB find response missing movie_results')
        if len(results) != 1:
            return None, 'not found' if not results else 'ambiguous TMDB match'
        tmdb_id = results[0].get('id') if isinstance(results[0], dict) else None
        if type(tmdb_id) is not int or tmdb_id <= 0:
            raise ProviderError('Invalid TMDB movie identifier')
        details = self.get(f'movie/{tmdb_id}', language='en-US', append_to_response='credits')
        if details.get('id') != tmdb_id or details.get('imdb_id') != imdb_id:
            return None, 'TMDB identity mismatch'
        return details, ''


def read_mapping(stream: TextIO) -> dict[str, str]:
    reader = csv.DictReader(stream, strict=True)
    if not reader.fieldnames or not {'film', 'imdb'}.issubset(reader.fieldnames) or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError('Use the corrected Wikidata CSV containing film and imdb columns')
    mapping, reverse = {}, {}
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError('Incorrect number of CSV fields')
        raw = QID.fullmatch(clean(row.get('film')))
        imdb = clean(row.get('imdb'))
        if not raw or not IMDB.fullmatch(imdb):
            raise ValueError('Invalid Wikidata/IMDb identity in snapshot')
        qid = raw[1]
        if qid in mapping or imdb in reverse:
            raise ValueError('Duplicate or ambiguous Wikidata/IMDb mapping; review snapshot')
        mapping[qid] = imdb
        reverse[imdb] = qid
    if not mapping:
        raise ValueError('Snapshot contains no identities')
    return mapping


@dataclass
class Report:
    candidates: int = 0
    matched: int = 0
    unmapped_local: int = 0
    snapshot_only: int = 0
    skipped: int = 0
    fields_filled: int = 0
    people_created: int = 0
    credits_created: int = 0
    links_created: int = 0
    dry_run: bool = True
    issues: list[str] = field(default_factory=list)


def valid_text(value, limit):
    if not isinstance(value, str):
        return ''
    value = value.strip()
    return value if value and len(value) <= limit and '\x00' not in value else ''


def link_movie(db, movie, source, external_id, report):
    existing = db.get(MovieSource, (source, external_id))
    own = db.scalar(select(MovieSource).where(MovieSource.source == source, MovieSource.movie_id == movie.id))
    if (existing and existing.movie_id != movie.id) or (own and own.external_id != external_id):
        return False
    if not existing:
        db.add(MovieSource(source=source, external_id=external_id, movie_id=movie.id))
        db.flush()
        report.links_created += 1
    return True


def person_for(db, entry, report):
    external = entry.get('id')
    name = valid_text(entry.get('name'), 240)
    if type(external) is not int or external <= 0 or not name:
        return None
    external = str(external)
    source = db.get(PersonSource, ('tmdb', external))
    if source:
        return source.person_id
    # Do not guess the identity of a manually created person with the same name.
    manual = db.scalar(select(Person.id).where(Person.name.ilike(name.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_'), escape='\\'),
        ~select(PersonSource.person_id).where(PersonSource.person_id == Person.id).exists()))
    if manual is not None:
        report.issues.append(f'Manual person identity conflict: TMDB person {external}')
        return None
    person = Person(name=name)
    db.add(person)
    db.flush()
    db.add(PersonSource(source='tmdb', external_id=external, person_id=person.id))
    db.flush()
    report.people_created += 1
    return person.id


def record_field(db, movie, name, external):
    key = (movie.id, name, 'tmdb')
    if not db.get(MovieEnrichmentField, key):
        db.add(MovieEnrichmentField(movie_id=movie.id, field=name, source='tmdb', external_id=external))
        db.flush()


def apply_details(db, movie, details, provider, report, cast_limit):
    external = str(details['id'])
    overview = valid_text(details.get('overview'), 10000)
    path = details.get('poster_path')
    poster = provider.poster_base + path if isinstance(path, str) and IMAGE_PATH.fullmatch(path) else ''
    runtime = details.get('runtime')
    for name, value in [('synopsis', overview), ('poster_url', poster),
                        ('runtime', runtime if type(runtime) is int and 1 <= runtime <= 10000 else None)]:
        if value and not getattr(movie, name) and not db.get(MovieEnrichmentField, (movie.id, name, 'tmdb')):
            setattr(movie, name, value)
            record_field(db, movie, name, external)
            report.fields_filled += 1
    credits = details.get('credits')
    if not isinstance(credits, dict) or not isinstance(credits.get('cast'), list) or not isinstance(credits.get('crew'), list):
        raise ProviderError('TMDB movie details missing valid credits')
    occupied = set(db.scalars(select(MovieCredit.role).where(MovieCredit.movie_id == movie.id)))
    entries = [('actor', x) for x in credits['cast'][:cast_limit] if isinstance(x, dict)]
    entries += [(ROLES[x['job']], x) for x in credits['crew'] if isinstance(x, dict) and isinstance(x.get('job'), str) and x['job'] in ROLES]
    seen = set()
    for role, entry in entries:
        if role in occupied:
            continue
        # If a previously imported role was later removed, do not restore it automatically.
        if db.get(MovieEnrichmentField, (movie.id, 'credits_' + role, 'tmdb')):
            continue
        person_id = person_for(db, entry, report)
        if person_id is None:
            continue
        character = valid_text(entry.get('character'), 240) if role == 'actor' else ''
        key = (role, person_id, character)
        if key in seen:
            continue
        seen.add(key)
        db.add(MovieCredit(movie_id=movie.id, person_id=person_id, role=role, character=character))
        report.credits_created += 1
    for role in {r for r, _, _ in seen}:
        record_field(db, movie, 'credits_' + role, external)
    db.flush()


def enrich(db: Session, mapping, provider, *, limit=None, cast_limit=12, dry_run=True):
    """Caller owns transaction. Run one importer at a time and avoid concurrent catalog edits."""
    report = Report(dry_run=dry_run)
    sources = list(db.scalars(select(MovieSource).where(MovieSource.source == 'wikidata').order_by(MovieSource.movie_id)))
    local_ids = {s.external_id for s in sources}
    report.unmapped_local = len(local_ids - mapping.keys())
    report.snapshot_only = len(mapping.keys() - local_ids)
    targets = [(s.movie_id, mapping[s.external_id]) for s in sources if s.external_id in mapping]
    if limit is not None:
        targets = targets[:limit]
    report.candidates = len(targets)
    if not targets:
        return report
    provider.configuration()
    for movie_id, imdb in targets:
        details, reason = provider.movie(imdb)
        if details is None:
            report.skipped += 1
            report.issues.append(f'{imdb}: {reason}')
            continue
        movie = db.scalar(select(Movie).where(Movie.id == movie_id).with_for_update())
        if not movie:
            report.skipped += 1
            report.issues.append(f'{imdb}: movie no longer exists')
            continue
        # Check both identities before creating either link.
        keys = [('imdb', imdb), ('tmdb', str(details['id']))]
        conflict = False
        for source, ext in keys:
            old = db.get(MovieSource, (source, ext))
            own = db.scalar(select(MovieSource).where(MovieSource.source == source, MovieSource.movie_id == movie.id))
            if (old and old.movie_id != movie.id) or (own and own.external_id != ext):
                conflict = True
        if conflict:
            report.skipped += 1
            report.issues.append(f'{imdb}: conflicting external identity')
            continue
        # Reject large year disagreements (release dates may differ by one year).
        date = details.get('release_date')
        if isinstance(date, str) and re.match(r'^\d{4}-', date) and abs(int(date[:4]) - movie.year) > 1:
            report.skipped += 1
            report.issues.append(f'{imdb}: release year mismatch')
            continue
        for source, ext in keys:
            link_movie(db, movie, source, ext, report)
        apply_details(db, movie, details, provider, report, cast_limit)
        report.matched += 1
    return report
