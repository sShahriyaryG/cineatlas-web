"""Track external person identities and metadata import history."""
from alembic import op
import sqlalchemy as sa

revision = '0004_enrichment_sources'
down_revision = '0003_catalog_relations'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('person_sources',
        sa.Column('source', sa.String(32), primary_key=True),
        sa.Column('external_id', sa.String(64), primary_key=True),
        sa.Column('person_id', sa.Integer, sa.ForeignKey('persons.id', ondelete='CASCADE'), nullable=False),
        sa.UniqueConstraint('source', 'person_id', name='uq_person_sources_source_person'))
    op.create_index('ix_person_sources_person_id', 'person_sources', ['person_id'])
    op.create_table('movie_enrichment_fields',
        sa.Column('movie_id', sa.Integer, sa.ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('field', sa.String(32), primary_key=True),
        sa.Column('source', sa.String(32), primary_key=True),
        sa.Column('external_id', sa.String(64), nullable=False),
        sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('movie_enrichment_fields')
    op.drop_table('person_sources')
