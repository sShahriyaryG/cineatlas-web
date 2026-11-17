"""Initial relational schema.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
from app.db import Base
from app import models
revision='0001_initial'
down_revision=None
branch_labels=None
depends_on=None

# Pin the initial table set: later models must not be created by this revision.
_INITIAL_TABLES = ('users', 'movies', 'ratings', 'reviews', 'watchlist', 'edit_suggestions', 'reports')

def upgrade():
    Base.metadata.create_all(bind=op.get_bind(), tables=[Base.metadata.tables[name] for name in _INITIAL_TABLES])

def downgrade():
    Base.metadata.drop_all(bind=op.get_bind(), tables=[Base.metadata.tables[name] for name in _INITIAL_TABLES])
