"""Composable catalog search; only literal text is used in LIKE patterns."""
from typing import Literal
from sqlalchemy import and_, case, func, or_, select
from .catalog import genre_key
from .models import Genre, Movie, MovieCredit, Person, Rating
from .directory import CLASSIFICATIONS

SearchMode = Literal['title', 'synopsis', 'actor', 'director', 'all']
SortMode = Literal['relevance', 'title', 'newest', 'oldest', 'rating', 'most_rated']
GenreMode = Literal['and', 'or']


def escape_like(text: str) -> str:
    # Use a portable explicit escape rather than relying on database defaults.
    return text.replace('!', '!!').replace('%', '!%').replace('_', '!_')


def person_match(pattern, roles):
    return Movie.credits.any(and_(MovieCredit.role.in_(roles),
                                  MovieCredit.person.has(Person.name.ilike(pattern, escape='!'))))


def catalog_page(db, *, q, mode, genres, genre_mode, year, year_min, year_max,
                 rating_min, rating_max, sort, page, size, classifications=None, scope=None):
    """Return matching movies and aggregate ratings with deterministic pagination."""
    ratings = select(Rating.movie_id.label('mid'), func.avg(Rating.score).label('avg'),
                     func.count(Rating.id).label('n')).group_by(Rating.movie_id).subquery()
    count = func.coalesce(ratings.c.n, 0)
    stmt = select(Movie, ratings.c.avg, count).outerjoin(ratings, ratings.c.mid == Movie.id)
    q = ' '.join(q.split())
    terms = q.split()
    for term in terms:
        pattern = '%' + escape_like(term) + '%'
        title = Movie.title.ilike(pattern, escape='!')
        synopsis = Movie.synopsis.ilike(pattern, escape='!')
        if mode == 'title': condition = title
        elif mode == 'synopsis': condition = synopsis
        elif mode in ('actor', 'director'): condition = person_match(pattern, [mode])
        else: condition = or_(title, synopsis, person_match(pattern, ['actor', 'director']))
        stmt = stmt.where(condition)
    keys = sorted({genre_key(g) for g in genres if g.strip()})
    if keys:
        if genre_mode == 'or':
            stmt = stmt.where(Movie.genre_entries.any(Genre.key.in_(keys)))
        else:
            for key in keys:
                stmt = stmt.where(Movie.genre_entries.any(Genre.key == key))
    # Independent EXISTS predicates avoid duplicate rows (e.g. original and spoken languages).
    if scope is not None:
        category, ident = scope
        _, link, fk = CLASSIFICATIONS[category]
        stmt = stmt.where(select(link.movie_id).where(link.movie_id == Movie.id, fk == ident).exists())
    for category, (ids, matching) in (classifications or {}).items():
        _, link, fk = CLASSIFICATIONS[category]
        ids = sorted(set(ids))
        if not ids:
            continue
        if matching == 'or':
            stmt = stmt.where(select(link.movie_id).where(link.movie_id == Movie.id, fk.in_(ids)).exists())
        else:
            for ident in ids:
                stmt = stmt.where(select(link.movie_id).where(link.movie_id == Movie.id, fk == ident).exists())
    if year is not None: stmt = stmt.where(Movie.year == year)
    if year_min is not None: stmt = stmt.where(Movie.year >= year_min)
    if year_max is not None: stmt = stmt.where(Movie.year <= year_max)
    if rating_min is not None: stmt = stmt.where(ratings.c.avg >= rating_min)
    if rating_max is not None: stmt = stmt.where(ratings.c.avg <= rating_max)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    if sort == 'newest': stmt = stmt.order_by(Movie.year.desc())
    elif sort == 'oldest': stmt = stmt.order_by(Movie.year)
    elif sort == 'rating': stmt = stmt.order_by(case((ratings.c.avg.is_(None), 1), else_=0), ratings.c.avg.desc(), count.desc())
    elif sort == 'most_rated': stmt = stmt.order_by(count.desc())
    elif sort == 'relevance' and q:
        phrase = escape_like(q)
        # Title modes weight exact, prefix, phrase and token-only matches;
        # other scopes weight contiguous phrase matches within their own fields.
        if mode in ('title', 'all'):
            rank = case((Movie.title.ilike(phrase, escape='!'), 0),
                        (Movie.title.ilike(phrase+'%', escape='!'), 1),
                        (Movie.title.ilike('%'+phrase+'%', escape='!'), 2),
                        (and_(*(Movie.title.ilike('%'+escape_like(t)+'%', escape='!') for t in terms)), 3),
                        else_=4)
        elif mode == 'synopsis':
            rank = case((Movie.synopsis.ilike('%'+phrase+'%', escape='!'), 0), else_=1)
        else:
            rank = case((person_match(phrase, [mode]), 0),
                        (person_match(phrase+'%', [mode]), 1),
                        (person_match('%'+phrase+'%', [mode]), 2), else_=3)
        stmt = stmt.order_by(rank)
    stmt = stmt.order_by(func.lower(Movie.title), Movie.id)
    return db.execute(stmt.offset((page-1)*size).limit(size)).all(), total
