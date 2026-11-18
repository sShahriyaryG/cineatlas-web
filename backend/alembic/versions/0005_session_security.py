"""Add durable sessions, authentication quotas and security events."""
from alembic import op
import sqlalchemy as sa

revision = '0005_session_security'
down_revision = '0004_enrichment_sources'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auth_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('transport', sa.String(8), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True)),
        sa.Column('device', sa.String(240), nullable=False),
        sa.CheckConstraint("transport IN ('cookie','bearer')", name='valid_session_transport'))
    op.create_index('ix_auth_sessions_user_id', 'auth_sessions', ['user_id'])
    op.create_index('ix_auth_sessions_expires_at', 'auth_sessions', ['expires_at'])
    op.create_table('auth_attempts',
        sa.Column('key', sa.String(64), primary_key=True),
        sa.Column('bucket', sa.Integer, primary_key=True),
        sa.Column('count', sa.Integer, nullable=False),
        sa.CheckConstraint('count >= 1', name='valid_auth_attempt_count'))
    op.create_table('security_events',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('kind', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_security_events_user_id', 'security_events', ['user_id'])
    op.create_index('ix_security_events_created_at', 'security_events', ['created_at'])


def downgrade():
    op.drop_table('security_events')
    op.drop_table('auth_attempts')
    op.drop_table('auth_sessions')
