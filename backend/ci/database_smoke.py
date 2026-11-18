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
    from app.models import MovieCredit, Person
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
            VALUES (:title, 2020, :genres, :synopsis, '', 100, 'English', '') RETURNING id
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
        assert checked_json(client.get('/api/movies', params={'rating_min': 8}))['total'] == 1
        checked_json(client.put(f'/api/me/watchlist/{movie_id}', headers=headers))
        assert len(checked_json(client.get('/api/me/watchlist', headers=headers))) == 1
        sessions = checked_json(client.get('/api/auth/sessions', headers=headers))
        assert len(sessions) == 1 and sessions[0]['current'] is True
        assert client.post('/api/auth/logout', headers=headers).status_code == 204
        assert client.get('/api/auth/me', headers=headers).status_code == 401
    print('PASS: durable session creation and revocation.', flush=True)
    print('PASS: legacy genre backfill, title/synopsis/director search, filmography, auth, rating and watchlist.', flush=True)
    engine.dispose()


if __name__ == '__main__':
    main()
