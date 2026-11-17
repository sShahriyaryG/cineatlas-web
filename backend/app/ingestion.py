"""Validate a Wikidata SPARQL CSV snapshot and insert missing catalog movies."""
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import TextIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Movie, MovieSource

SOURCE = 'wikidata'
COLUMNS = {'film', 'title', 'year', 'genres', 'runtime'}
QID = re.compile(r'(?:https?://www\.wikidata\.org/entity/)?(Q[1-9][0-9]*)\Z')


def clean(value: str | None) -> str:
    return ' '.join(unicodedata.normalize('NFKC', value or '').split())


def title_key(title: str, year: int) -> tuple[str, int]:
    return clean(title).casefold(), year


def genres_from(value: str) -> str:
    # Keep source vocabulary, with a few consistent labels for existing UI filters.
    aliases = {'science fiction film': 'Science Fiction', 'science fiction': 'Science Fiction',
               'sci-fi': 'Science Fiction', 'action film': 'Action', 'comedy film': 'Comedy',
               'drama film': 'Drama', 'horror film': 'Horror', 'thriller film': 'Thriller',
               'animated film': 'Animation', 'adventure film': 'Adventure', 'crime film': 'Crime',
               'romance film': 'Romance', 'fantasy film': 'Fantasy', 'western film': 'Western',
               'documentary film': 'Documentary', 'film noir': 'Film Noir'}
    result: dict[str, str] = {}
    for raw in value.split('|'):
        label = clean(raw).replace(',', ' / ')
        if label:
            label = aliases.get(label.casefold(), label.title())
            result.setdefault(label.casefold(), label)
    chosen: list[str] = []
    for label in sorted(result.values(), key=str.casefold):
        if len(','.join([*chosen, label])) <= 255:
            chosen.append(label)
    return ','.join(chosen)


@dataclass(frozen=True)
class FilmRecord:
    source_id: str
    title: str
    year: int
    genres: str
    runtime: int | None


def normalize(row: dict[str, str]) -> FilmRecord:
    match = QID.fullmatch(clean(row.get('film')))
    if not match or len(match[1]) > 64:
        raise ValueError('invalid Wikidata entity ID')
    title = clean(row.get('title'))
    if not title or len(title) > 240 or any(ord(c) < 32 for c in title):
        raise ValueError('missing or invalid title')
    year_text = clean(row.get('year'))
    if not re.fullmatch(r'[0-9]{4}', year_text) or not 1888 <= int(year_text) <= 2200:
        raise ValueError('invalid release year')
    raw_runtime = clean(row.get('runtime'))
    runtime = None
    if raw_runtime:
        try:
            number = Decimal(raw_runtime)
            if not number.is_finite() or not 1 <= number <= 10000 or number != number.to_integral_value():
                raise ValueError('invalid runtime (whole minutes expected)')
            runtime = int(number)
        except InvalidOperation as exc:
            raise ValueError('invalid runtime') from exc
    return FilmRecord(match[1], title, int(year_text), genres_from(row.get('genres') or ''), runtime)


@dataclass
class ImportReport:
    rows: int = 0
    inserted: int = 0
    existing_source: int = 0
    duplicate_input: int = 0
    title_year_conflicts: int = 0
    invalid: int = 0
    dry_run: bool = False
    issues: list[str] = field(default_factory=list)

    def issue(self, line: int, reason: str) -> None:
        if len(self.issues) < 30:
            self.issues.append(f'CSV line {line}: {reason}')


def ingest(db: Session, stream: TextIO, *, dry_run: bool = False, strict: bool = False) -> ImportReport:
    """Add records only. Never update/link/delete existing movies automatically.

    Transaction owned by caller; dry-run does not stage database changes.
    Run one importer at a time. A failed insert must roll back the transaction.
    """
    reader = csv.DictReader(stream, strict=True)
    if reader.fieldnames is None or not COLUMNS.issubset(reader.fieldnames) or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError('CSV must include unique headers: film,title,year,genres,runtime')
    report = ImportReport(dry_run=dry_run)
    known_ids = set(db.scalars(select(MovieSource.external_id).where(MovieSource.source == SOURCE)))
    known_titles = {title_key(title, year) for title, year in db.execute(select(Movie.title, Movie.year))}
    seen: set[str] = set()
    for line, row in enumerate(reader, 2):
        report.rows += 1
        try:
            if None in row or any(row.get(column) is None for column in COLUMNS):
                raise ValueError('incorrect number of CSV fields')
            record = normalize(row)
        except ValueError as exc:
            report.invalid += 1
            report.issue(line, str(exc))
            continue
        if record.source_id in seen:
            report.duplicate_input += 1
            continue
        seen.add(record.source_id)
        if record.source_id in known_ids:
            report.existing_source += 1
            continue
        key = title_key(record.title, record.year)
        if key in known_titles:
            report.title_year_conflicts += 1
            report.issue(line, f'{record.source_id}: existing title/year; manual review required')
            continue
        if not dry_run:
            movie = Movie(title=record.title, year=record.year, genres=record.genres, runtime=record.runtime)
            db.add(movie)
            db.flush()
            db.add(MovieSource(source=SOURCE, external_id=record.source_id, movie_id=movie.id))
        known_titles.add(key)
        known_ids.add(record.source_id)
        report.inserted += 1
    if strict and report.invalid:
        raise ValueError(f'{report.invalid} invalid row(s); strict import aborted')
    return report
