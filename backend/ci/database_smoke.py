"""Exercise real Alembic migrations and API against an EMPTY, disposable database.

Run from backend/ as python -m ci.database_smoke --require-postgresql.
Unlike pytest, this script never invokes the SQLite-resetting test fixture.
"""
import argparse
import os

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text


def checked_json(response, expected_status=200):
    assert response.status_code == expected_status, response.text
    return response.json()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-postgresql', action='store_true')
    args = parser.parse_args()
    if not os.environ.get('DATABASE_URL'):
        raise SystemExit('Set DATABASE_URL explicitly to an empty, disposable CI database.')

    from app.db import Base, SessionLocal, engine
    from app import models
    from app.models import MovieCredit, Person, User, MovieMetadataOverride
    from fastapi.testclient import TestClient

    if args.require_postgresql and engine.dialect.name != 'postgresql':
        raise SystemExit('The PostgreSQL CI check must use a real PostgreSQL database.')
    if inspect(engine).get_table_names():
        raise SystemExit('Refusing to run against a non-empty database. Use a fresh CI database.')

    config = Config('alembic.ini')
    # Stage a pre-normalization record, then verify the real 0003 backfill.
    command.upgrade(config, '0002_movie_sources')
    with engine.begin() as conn:
        movie_id = conn.execute(text('''
            INSERT INTO movies (title, year, genres, synopsis, poster_url, runtime, language, country)
            VALUES (:title, 2020, :genres, :synopsis, '', 100, 'English', 'France') RETURNING id
        '''), {'title': 'CI Legacy Film', 'genres': 'Sci-Fi, Drama, science fiction film',
               'synopsis': 'A twist in the story'}).scalar_one()
    command.upgrade(config, 'head')
    command.upgrade(config, 'head')  # A repeated upgrade is a no-op.

    # Inspect before starting FastAPI: its development lifespan calls create_all.
    with engine.connect() as conn:
        expected_head = ScriptDirectory.from_config(config).get_current_head()
        assert MigrationContext.configure(conn).get_current_revision() == expected_head
    schema = inspect(engine)
    for name, table in Base.metadata.tables.items():
        actual = {col['name'] for col in schema.get_columns(name)}
        assert set(table.columns.keys()) == actual, f'Column mismatch: {name}'
    command.check(config)
    print('PASS: migration chain reaches head, repeats safely, and matches model metadata.', flush=True)

    with SessionLocal() as db:
        person = Person(name='CI Example Director', biography='Synthetic test data')
        db.add(person)
        db.flush()
        person_id = person.id
        db.add(MovieCredit(movie_id=movie_id, person_id=person_id, role='director', character=''))
        db.commit()

    from app.main import app
    with TestClient(app) as client:
        assert checked_json(client.get('/api/health')) == {'status': 'ok'}
        movie = checked_json(client.get(f'/api/movies/{movie_id}'))
        assert movie['title'] == 'CI Legacy Film'
        assert movie['synopsis'] == 'A twist in the story'
        assert movie['genres'] == ['Drama', 'Science Fiction']
        assert movie['language'] == 'English' and movie['country'] == 'France'
        assert movie['production_countries'] == ['France']
        assert movie['unspecified_languages'] == ['English'] and movie['original_language'] is None
        assert checked_json(client.get('/api/movies', params={'q': 'twi'}))['total'] == 0
        assert checked_json(client.get('/api/movies', params={'q': 'twi', 'mode': 'synopsis'}))['total'] == 1
        assert checked_json(client.get('/api/movies', params={'q': 'Example Director', 'mode': 'director'}))['total'] == 1
        assert checked_json(client.get('/api/movies', params={'genres': ['Drama', 'Sci-Fi']}))['total'] == 1
        assert checked_json(client.get(f'/api/persons/{person_id}'))['credits'][0]['movie_id'] == movie_id
        result = checked_json(client.post('/api/auth/register', json={
            'username': 'ci_member', 'email': 'ci-member@example.org',
            'password': 'synthetic-test-password-123',
        }), 201)
        headers = {'Authorization': 'Bearer ' + result['token']}
        rated = checked_json(client.put(f'/api/movies/{movie_id}/rating', json={'score': 9}, headers=headers))
        assert rated['average_rating'] == 9 and rated['rating_count'] == 1
        personal = checked_json(client.get('/api/me/ratings', headers=headers))
        assert [(m['id'],m['my_score']) for m in personal] == [(movie_id,9)]
        assert checked_json(client.get('/api/movies', params={'rating_min': 8}))['total'] == 1
        checked_json(client.put(f'/api/me/watchlist/{movie_id}', headers=headers))
        assert len(checked_json(client.get('/api/me/watchlist', headers=headers))) == 1
        sessions = checked_json(client.get('/api/auth/sessions', headers=headers))
        assert len(sessions) == 1 and sessions[0]['current'] is True
        # First verify the normal member cannot directly alter catalog metadata.
        metadata_path = f'/api/movies/{movie_id}/metadata'
        assert client.patch(metadata_path, json={'original_language':'English'}, headers=headers).status_code == 403
        # Promote the disposable account to exercise admin endpoints; role is
        # checked on every request so no new token is required.
        with SessionLocal() as db:
            db.get(User,result['user']['id']).role='admin'; db.commit()
        enriched=checked_json(client.patch(metadata_path,headers=headers,json={
            'original_language':'English','spoken_languages':['English','French'],
            'production_countries':['France','Canada'],'tags':['Fixture'],
            'certifications':[{'country':'Canada','rating':'PG'}],
            'quotes':[{'quote':'Synthetic CI quotation','spoiler':True}]
        }))
        assert enriched['original_language']=='English' and enriched['unspecified_languages']==[]
        assert enriched['production_countries']==['Canada','France'] and enriched['certifications'][0]['rating']=='PG'
        assert enriched['quotes'][0]['spoiler'] is True
        assert checked_json(client.patch(metadata_path,headers=headers,json={'quotes':[]}))['quotes']==[]
        with SessionLocal() as db:
            assert db.get(MovieMetadataOverride,(movie_id,'quotes')) is not None
        person_meta=checked_json(client.patch(f'/api/persons/{person_id}/metadata',headers=headers,json={
            'birthday':'1980-01-01','birthplace':'Synthetic City','nationalities':['Canada']
        }))
        assert person_meta['birthday']=='1980-01-01' and person_meta['nationalities']==['Canada']
        checked_json(client.post(f'/api/movies/{movie_id}/credits',headers=headers,json={'person_id':person_id,'role':'composer'}),201)
        assert {c['role'] for c in checked_json(client.get(f'/api/persons/{person_id}'))['credits']}=={'director','composer'}
        assert client.post('/api/auth/logout', headers=headers).status_code == 204
        assert client.get('/api/auth/me', headers=headers).status_code == 401
    # Exercise enrichment on the migrated database without HTTP or secrets.
    from app.enrichment_v2 import enrich_linked
    from app.models import Movie, MovieSource, PersonSource, PersonEnrichmentField, MovieEnrichmentField
    from app.metadata import movie_metadata_out, person_metadata_out
    from sqlalchemy import select, func

    class FixtureProvider:
        poster_base='https://image.tmdb.org/t/p/w500'
        profile_base='https://image.tmdb.org/t/p/w185'
        languages={'en':'English'}
        countries={'CA':'Canada'}
        def configuration(self): pass
        def linked_movie(self, external):
            return {'id':int(external),'imdb_id':'tt0000007','release_date':'2020-01-01',
                    'original_language':'en','production_countries':[{'iso_3166_1':'CA'}],
                    'credits':{'cast':[{'id':42,'name':'CI Synthetic Actor','character':'Fixture'}],'crew':[]}}
        def linked_person(self, external):
            return {'id':int(external),'biography':'Fixture biography','profile_path':'/fixture.jpg'}

    with SessionLocal() as db:
        film=Movie(title='Synthetic enrichment film',year=2020)
        db.add(film); db.flush(); fid=film.id
        db.add_all([MovieSource(source='tmdb',external_id='7',movie_id=fid),
                    MovieSource(source='imdb',external_id='tt0000007',movie_id=fid)])
        db.commit()
        r=enrich_linked(db,FixtureProvider())
        assert r.matched==1 and r.person_fields_filled==2
        db.rollback()
        assert db.scalar(select(func.count()).select_from(PersonEnrichmentField))==0
        assert movie_metadata_out(db,db.get(Movie,fid))['original_language'] is None
        enrich_linked(db,FixtureProvider(),dry_run=False); db.commit()
        assert movie_metadata_out(db,db.get(Movie,fid))['production_countries']==['Canada']
        pid=db.get(PersonSource,('tmdb','42')).person_id
        assert person_metadata_out(db,db.get(Person,pid))['profile_url'].endswith('/fixture.jpg')
        assert db.get(PersonEnrichmentField,(pid,'biography','tmdb')) is not None
        assert db.get(MovieEnrichmentField,(fid,'production_countries','tmdb')) is not None
        r=enrich_linked(db,FixtureProvider(),dry_run=False); db.commit()
        assert r.fields_filled==r.person_fields_filled==r.credits_created==0
    print('PASS: extended enrichment preview rollback, import provenance and idempotency.', flush=True)
    print('PASS: legacy language/country backfill, metadata permissions, manual overrides and extended credit roles.', flush=True)
    print('PASS: durable session creation and revocation.', flush=True)
    print('PASS: legacy genre backfill, title/synopsis/director search, filmography, auth, rating and watchlist.', flush=True)
    engine.dispose()


if __name__ == '__main__':
    main()
