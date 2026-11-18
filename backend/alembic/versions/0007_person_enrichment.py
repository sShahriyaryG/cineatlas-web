"""Extend field-level import history to people."""
from alembic import op
import sqlalchemy as sa

revision = '0007_person_enrichment'
down_revision = '0006_catalog_metadata'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('person_enrichment_fields',
        sa.Column('person_id', sa.Integer, sa.ForeignKey('persons.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('field', sa.String(32), primary_key=True),
        sa.Column('source', sa.String(32), primary_key=True),
        sa.Column('external_id', sa.String(64), nullable=False),
        sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('person_enrichment_fields')
