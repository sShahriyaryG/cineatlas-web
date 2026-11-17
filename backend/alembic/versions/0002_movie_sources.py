"""Track catalog source identifiers without changing existing movie IDs.

Revision ID: 0002_movie_sources
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_movie_sources'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'movie_sources',
        sa.Column('source', sa.String(32), primary_key=True),
        sa.Column('external_id', sa.String(64), primary_key=True),
        sa.Column('movie_id', sa.Integer, sa.ForeignKey('movies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('source', 'movie_id', name='uq_movie_sources_source_movie'),
    )
    op.create_index('ix_movie_sources_movie_id', 'movie_sources', ['movie_id'])


def downgrade():
    op.drop_index('ix_movie_sources_movie_id', table_name='movie_sources')
    op.drop_table('movie_sources')
