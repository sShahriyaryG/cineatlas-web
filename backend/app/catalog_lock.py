"""Serialize catalog API mutations and editorial approval on PostgreSQL."""
from sqlalchemy import text


def lock_catalog(db):
    if db.get_bind().dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(61271983)'))
