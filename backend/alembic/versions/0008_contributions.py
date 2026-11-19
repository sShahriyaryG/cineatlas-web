"""Persistent editorial contributions; existing synopsis proposals stay intact."""
from alembic import op
import sqlalchemy as sa

revision = '0008_contributions'
down_revision = '0007_person_enrichment'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('movie_credits', sa.Column('position', sa.Integer, nullable=True))
    op.create_table('contributions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('author_name', sa.String(40), nullable=False),
        sa.Column('entity', sa.String(8), nullable=False),
        sa.Column('target_id', sa.Integer), sa.Column('result_id', sa.Integer),
        sa.Column('status', sa.String(12), nullable=False),
        sa.Column('baseline', sa.Text, nullable=False), sa.Column('changes', sa.Text, nullable=False),
        sa.Column('reason', sa.Text, nullable=False), sa.Column('source_url', sa.String(600)),
        sa.Column('reviewer_id', sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('reviewer_name', sa.String(40)), sa.Column('review_note', sa.Text, nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("entity IN ('movie','person')", name='valid_contribution_entity'),
        sa.CheckConstraint("status IN ('draft','pending','approved','rejected','withdrawn')", name='valid_contribution_status'))
    op.create_index('ix_contributions_user_id', 'contributions', ['user_id'])
    op.create_index('ix_contributions_status', 'contributions', ['status'])


def downgrade():
    op.drop_table('contributions')
    op.drop_column('movie_credits', 'position')
