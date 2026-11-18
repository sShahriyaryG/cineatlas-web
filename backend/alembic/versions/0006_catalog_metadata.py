"""Add optional metadata, classifications and extended credit roles."""
import unicodedata
from alembic import op
import sqlalchemy as sa

revision = '0006_catalog_metadata'
down_revision = '0005_session_security'
branch_labels = None
depends_on = None

OLD_ROLES = "role IN ('actor','director','writer','producer')"
NEW_ROLES = "role IN ('actor','director','writer','producer','composer','cinematographer','editor','other')"


def owner(name):
    return sa.Column(f'{name}_id', sa.Integer, sa.ForeignKey(f'{name}s.id', ondelete='CASCADE'), primary_key=True)


def label_ref(name):
    return sa.Column(f'{name}_id', sa.Integer, sa.ForeignKey(f'{name}s.id' if name != 'country' else 'countries.id', ondelete='RESTRICT'), primary_key=True)


def vocabulary(name, code=False):
    columns = [sa.Column('id', sa.Integer, primary_key=True), sa.Column('key', sa.String(480), nullable=False, unique=True), sa.Column('name', sa.String(120), nullable=False)]
    if code:
        columns.append(sa.Column('code', sa.String(12), unique=True))
    return op.create_table(name, *columns)


def link_index(table, field):
    op.create_index(f'ix_{table}_{field}', table, [field])


def upgrade():
    languages = vocabulary('languages', code=True)
    countries = vocabulary('countries', code=True)
    vocabulary('tags')
    ml = op.create_table('movie_languages', owner('movie'), label_ref('language'), sa.Column('kind', sa.String(12), primary_key=True),
        sa.CheckConstraint("kind IN ('original','spoken','unspecified')", name='valid_movie_language_kind'))
    link_index('movie_languages', 'language_id')
    op.create_index('uq_movie_original_language', 'movie_languages', ['movie_id'], unique=True,
                    postgresql_where=sa.text("kind = 'original'"), sqlite_where=sa.text("kind = 'original'"))
    mc = op.create_table('movie_countries', owner('movie'), label_ref('country'))
    link_index('movie_countries', 'country_id')
    op.create_table('movie_tags', owner('movie'), label_ref('tag'))
    link_index('movie_tags', 'tag_id')
    op.create_table('movie_metadata', owner('movie'), sa.Column('original_title', sa.String(240)),
        sa.Column('release_date', sa.Date), sa.Column('release_status', sa.String(16)), sa.Column('trailer_url', sa.String(600)),
        sa.CheckConstraint("release_status IN ('released','upcoming','in_production','cancelled')", name='valid_release_status'))
    op.create_table('movie_alternative_titles', owner('movie'), sa.Column('key', sa.String(480), primary_key=True), sa.Column('title', sa.String(240), nullable=False))
    op.create_table('movie_certifications', owner('movie'), label_ref('country'), sa.Column('rating', sa.String(32), primary_key=True))
    link_index('movie_certifications', 'country_id')
    op.create_table('movie_soundtracks', owner('movie'), sa.Column('position', sa.Integer, primary_key=True),
        sa.Column('title', sa.String(240), nullable=False), sa.Column('artist', sa.String(240), nullable=False),
        sa.Column('composer', sa.String(240), nullable=False), sa.Column('external_url', sa.String(600)),
        sa.CheckConstraint('position >= 0', name='valid_soundtrack_position'))
    op.create_table('movie_quotes', owner('movie'), sa.Column('position', sa.Integer, primary_key=True),
        sa.Column('quote', sa.String(500), nullable=False), sa.Column('speaker', sa.String(240), nullable=False),
        sa.Column('spoiler', sa.Boolean, nullable=False), sa.Column('source_url', sa.String(600)),
        sa.CheckConstraint('position >= 0', name='valid_quote_position'))
    op.create_table('person_metadata', owner('person'), sa.Column('full_name', sa.String(240)), sa.Column('profile_url', sa.String(600)),
        sa.Column('birthday', sa.Date), sa.Column('deathday', sa.Date), sa.Column('birthplace', sa.String(240)),
        sa.CheckConstraint('deathday IS NULL OR birthday IS NULL OR deathday >= birthday', name='valid_person_dates'))
    op.create_table('person_alternative_names', owner('person'), sa.Column('key', sa.String(480), primary_key=True), sa.Column('name', sa.String(240), nullable=False))
    op.create_table('person_nationalities', owner('person'), label_ref('country'))
    link_index('person_nationalities', 'country_id')
    for target in ('movie','person'):
        op.create_table(f'{target}_metadata_overrides', owner(target), sa.Column('field', sa.String(32), primary_key=True), sa.Column('edited_at', sa.DateTime(timezone=True), nullable=False))
    with op.batch_alter_table('movie_credits') as batch:
        batch.drop_constraint('valid_credit_role', type_='check')
        batch.create_check_constraint('valid_credit_role', NEW_ROLES)

    # Preserve raw legacy values exactly. Do not guess language type, ISO code,
    # or delimiters in a free-text field (e.g. a country name containing a comma).
    db = op.get_bind()
    movies = sa.table('movies', sa.column('id', sa.Integer), sa.column('language', sa.String), sa.column('country', sa.String))
    for field, vocabulary_table, links, link_field in [('language', languages, ml, 'language_id'), ('country', countries, mc, 'country_id')]:
        ids = {}
        for mid, value in db.execute(sa.select(movies.c.id, movies.c[field]).order_by(movies.c.id)):
            name = ' '.join(unicodedata.normalize('NFKC', value or '').split())
            if not name:
                continue
            # NFKC can expand a legacy value. Fall back to its original spelling
            # rather than truncating or losing a label during migration.
            if len(name) > 120 or len(name.casefold()) > 480:
                name = ' '.join((value or '').split())
            key = name.casefold()
            if key not in ids:
                ids[key] = db.execute(vocabulary_table.insert().values(key=key, name=name).returning(vocabulary_table.c.id)).scalar_one()
            values = {'movie_id': mid, link_field: ids[key]}
            if field == 'language':
                values['kind'] = 'unspecified'
            db.execute(links.insert().values(**values))


def downgrade():
    db = op.get_bind()
    if db.scalar(sa.text("SELECT count(*) FROM movie_credits WHERE NOT (" + OLD_ROLES + ")")):
        raise RuntimeError('Downgrade would invalidate extended credit roles; back up and resolve those records first.')
    with op.batch_alter_table('movie_credits') as batch:
        batch.drop_constraint('valid_credit_role', type_='check')
        batch.create_check_constraint('valid_credit_role', OLD_ROLES)
    # Explicit downgrade discards extension metadata, retaining legacy columns.
    for name in ('person_metadata_overrides','movie_metadata_overrides','person_nationalities','person_alternative_names','person_metadata','movie_quotes','movie_soundtracks','movie_certifications','movie_alternative_titles','movie_metadata','movie_tags','movie_countries','movie_languages','tags','countries','languages'):
        op.drop_table(name)
