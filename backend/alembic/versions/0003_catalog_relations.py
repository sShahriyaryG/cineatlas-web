"""Normalize genres and introduce people and movie credits."""
import unicodedata
from alembic import op
import sqlalchemy as sa

revision = '0003_catalog_relations'
down_revision = '0002_movie_sources'
branch_labels = None
depends_on = None

# Frozen backfill vocabulary, independent of future application changes.
ALIASES = {
    'sci-fi': 'Science Fiction', 'science fiction film': 'Science Fiction',
    'animated film': 'Animation', 'animation film': 'Animation', 'film noir': 'Film Noir',
    **{f'{label.lower()} film': label for label in (
        'Action', 'Adventure', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Fantasy',
        'Horror', 'Mystery', 'Romance', 'Thriller', 'War', 'Western', 'Musical', 'Family', 'Historical')},
}

def upgrade():
    genres = op.create_table('genres',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('key', sa.String(512), nullable=False, unique=True),
        sa.Column('name', sa.String(512), nullable=False))
    links = op.create_table('movie_genres',
        sa.Column('movie_id', sa.Integer, sa.ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('genre_id', sa.Integer, sa.ForeignKey('genres.id', ondelete='CASCADE'), primary_key=True))
    op.create_index('ix_movie_genres_genre_id', 'movie_genres', ['genre_id'])
    op.create_table('persons',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(240), nullable=False),
        sa.Column('biography', sa.Text, nullable=False))
    op.create_index('ix_persons_name', 'persons', ['name'])
    op.create_table('movie_credits',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('movie_id', sa.Integer, sa.ForeignKey('movies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('person_id', sa.Integer, sa.ForeignKey('persons.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(16), nullable=False),
        sa.Column('character', sa.String(240), nullable=False),
        sa.UniqueConstraint('movie_id', 'person_id', 'role', 'character', name='uq_movie_credit'),
        sa.CheckConstraint("role IN ('actor','director','writer','producer')", name='valid_credit_role'),
        sa.CheckConstraint("role = 'actor' OR character = ''", name='valid_credit_character'))
    op.create_index('ix_movie_credits_movie_id', 'movie_credits', ['movie_id'])
    op.create_index('ix_movie_credits_person_id', 'movie_credits', ['person_id'])
    db = op.get_bind()
    movies = sa.table('movies', sa.column('id', sa.Integer), sa.column('genres', sa.String))
    ids = {}
    for movie_id, text in db.execute(sa.select(movies.c.id, movies.c.genres).order_by(movies.c.id)):
        seen = set()
        for raw in (text or '').split(','):
            label = ' '.join(unicodedata.normalize('NFKC', raw).split())
            if not label:
                continue
            name = ALIASES.get(label.casefold(), label.title())
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            if key not in ids:
                ids[key] = db.execute(genres.insert().values(key=key, name=name).returning(genres.c.id)).scalar_one()
            db.execute(links.insert().values(movie_id=movie_id, genre_id=ids[key]))

def downgrade():
    # Old genre text was retained. New people/credits are lost on downgrade.
    op.drop_table('movie_credits')
    op.drop_table('persons')
    op.drop_table('movie_genres')
    op.drop_table('genres')
