"""Normalize genre vocabulary and maintain movie/genre links."""
import unicodedata
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from .models import Genre, Movie

ALIASES = {
    'sci-fi': 'Science Fiction', 'science fiction film': 'Science Fiction',
    'animated film': 'Animation', 'animation film': 'Animation', 'film noir': 'Film Noir',
    **{f'{label.lower()} film': label for label in (
        'Action', 'Adventure', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Fantasy',
        'Horror', 'Mystery', 'Romance', 'Thriller', 'War', 'Western', 'Musical', 'Family', 'Historical')},
}

def genre_name(value: str) -> str:
    label = ' '.join(unicodedata.normalize('NFKC', value).split())
    return ALIASES.get(label.casefold(), label.title())

def genre_key(value: str) -> str:
    return genre_name(value).casefold()

def parse_genres(value: str) -> dict[str, str]:
    result = {}
    for raw in value.split(','):
        name = genre_name(raw)
        if name:
            key = name.casefold()
            if len(name) > 512 or len(key) > 512 or "\x00" in name:
                raise ValueError("Invalid genre label (maximum 512 characters)")
            result.setdefault(key, name)
    return dict(sorted(result.items()))

def set_movie_genres(db, movie: Movie, value: str) -> None:
    """Replace links, retain old text for compatibility; caller commits."""
    names = parse_genres(value)
    insert = {'sqlite': sqlite_insert, 'postgresql': pg_insert}[db.get_bind().dialect.name]
    for key, name in names.items():
        db.execute(insert(Genre).values(key=key, name=name).on_conflict_do_nothing(index_elements=['key']))
    movie.genre_entries = list(db.scalars(select(Genre).where(Genre.key.in_(names)).order_by(Genre.key))) if names else []
    # Keep whole labels in the old 255-character column, never truncate a label.
    legacy = []
    for raw in value.split(','):
        label = raw.strip()
        if label and len(','.join([*legacy, label])) <= 255:
            legacy.append(label)
    movie.genres = ','.join(legacy)
