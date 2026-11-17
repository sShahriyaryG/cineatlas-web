"""Offline ingestion tests using deliberately fictional fixture records."""
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, func

from app.db import SessionLocal
from app.ingestion import ingest, normalize
from app.models import Movie, MovieSource, Rating, User

HEADER = 'film,title,year,genres,runtime\n'
VALID = HEADER + 'http://www.wikidata.org/entity/Q999999991,  Example Film  ,2000,action film|Action|science fiction film,120.0\n'


def load(db, text=VALID, **kwargs):
    return ingest(db, io.StringIO(text), **kwargs)


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_clean_insert_and_rerun_preserves_admin_edits():
    with SessionLocal() as db:
        first = load(db)
        db.commit()
        movie = db.scalar(select(Movie))
        assert (first.inserted, movie.title, movie.genres, movie.runtime) == (1, 'Example Film', 'Action,Science Fiction', 120)
        assert db.get(MovieSource, ('wikidata', 'Q999999991')).movie_id == movie.id
        movie.synopsis = 'Manual correction'
        db.commit()
        second = load(db)
        db.commit()
        assert second.existing_source == 1 and second.inserted == 0
        assert count(db, Movie) == 1 and movie.synopsis == 'Manual correction'


def test_dry_run_and_duplicate_input():
    with SessionLocal() as db:
        report = load(db, VALID + VALID.splitlines()[1] + '\n', dry_run=True)
        assert (report.rows, report.inserted, report.duplicate_input) == (2, 1, 1)
        assert not db.new and count(db, Movie) == 0 and count(db, MovieSource) == 0


def test_invalid_rows_and_existing_title_year_do_not_overwrite():
    with SessionLocal() as db:
        movie = Movie(title='EXAMPLE FILM', year=2000, synopsis='Keep me')
        db.add(movie)
        db.commit()
        user = User(username='fixture', email='fixture@example.org', password_hash='not-a-real-hash')
        db.add(user)
        db.flush()
        db.add(Rating(user_id=user.id, movie_id=movie.id, score=8))
        db.commit()
        report = load(db, VALID + 'bad,Invalid,2000,,\nQ999999992,Other,2001,,\nQ999999993,Nope,1000,,\n')
        db.commit()
        assert (report.inserted, report.title_year_conflicts, report.invalid) == (1, 1, 2)
        assert count(db, Movie) == 2 and count(db, MovieSource) == 1
        assert movie.synopsis == 'Keep me' and count(db, Rating) == 1
        assert db.scalar(select(Movie).where(Movie.title == 'Other')).genres == ''


def test_strict_mode_rollback_and_bad_header():
    with pytest.raises(ValueError, match='strict import aborted'):
        with SessionLocal() as db:
            load(db, VALID + 'bad,Invalid,2000,,\n', strict=True)
            db.commit()
    with SessionLocal() as db:
        assert count(db, Movie) == 0
        with pytest.raises(ValueError, match='headers'):
            load(db, 'title,year\nExample,2000\n')


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-1', '1.5', '10001', 'abc'])
def test_reject_invalid_runtime(value):
    with pytest.raises(ValueError, match='runtime'):
        normalize({'film': 'Q999999991', 'title': 'Example', 'year': '2000', 'genres': '', 'runtime': value})


def test_migration_fresh_and_existing_database(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    for existing in [False, True]:
        url = f'sqlite:///{tmp_path / ("old.db" if existing else "new.db")}'
        env = dict(os.environ, DATABASE_URL=url)
        engine = create_engine(url)
        def upgrade(revision):
            subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', revision], cwd=backend, env=env, check=True, capture_output=True)
        if existing:
            upgrade('0001_initial')
            assert 'movie_sources' not in inspect(engine).get_table_names()
            with engine.begin() as connection:
                connection.execute(Movie.__table__.insert().values(title='Existing', year=2001))
        upgrade('head')
        assert 'movie_sources' in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(Movie)) == int(existing)
        engine.dispose()


def test_imported_movie_visible_and_source_removed_on_admin_delete(client):
    with SessionLocal() as db:
        load(db)
        db.commit()
    result = client.get('/api/movies', params={'q': 'Example Film'})
    assert result.status_code == 200 and result.json()['total'] == 1
    movie_id = result.json()['items'][0]['id']
    assert result.json()['items'][0]['genres'] == ['Action', 'Science Fiction']
    login = client.post('/api/auth/register', json={'username': 'ingestadmin', 'email': 'ingest@example.org', 'password': 'test-password-long'})
    assert login.status_code == 201
    with SessionLocal() as db:
        db.scalar(select(User).where(User.username == 'ingestadmin')).role = 'admin'
        db.commit()
    headers = {'Authorization': 'Bearer ' + login.json()['token']}
    assert client.delete(f'/api/movies/{movie_id}', headers=headers).status_code == 204
    with SessionLocal() as db:
        assert count(db, MovieSource) == 0 and count(db, Movie) == 0


def test_fetch_validates_response_and_writes_snapshot(tmp_path, monkeypatch):
    from email.message import Message
    import ingest_movies

    class FakeResponse(io.BytesIO):
        def __init__(self, mime, data):
            super().__init__(data)
            self.headers = Message()
            self.headers['Content-Type'] = mime

    def fake_open(request, timeout):
        assert request.full_url.startswith('https://query.wikidata.org/sparql?')
        assert request.get_header('Accept') == 'text/csv'
        assert 'example.org' in request.get_header('User-agent')
        assert timeout == 90
        return FakeResponse('text/csv', VALID.encode())

    path = tmp_path / 'snapshot.csv'
    monkeypatch.setattr(ingest_movies, 'urlopen', fake_open)
    ingest_movies.fetch(path, 'https://example.org/project')
    assert path.read_text() == VALID
    with pytest.raises(ValueError, match='already exists'):
        ingest_movies.fetch(path, 'https://example.org/project')
    monkeypatch.setattr(ingest_movies, 'urlopen', lambda *args, **kwargs: FakeResponse('text/html', b'<html>Error</html>'))
    bad_path = tmp_path / 'bad.csv'
    with pytest.raises(ValueError, match='did not return CSV'):
        ingest_movies.fetch(bad_path, 'https://example.org/project')
    assert not bad_path.exists()


def test_cli_dry_run_commit_and_strict_error(tmp_path, capsys):
    import ingest_movies
    import json
    path = tmp_path / 'sample.csv'
    path.write_text(VALID, encoding='utf-8')
    assert ingest_movies.main(['import', str(path), '--dry-run', '--strict']) == 0
    assert json.loads(capsys.readouterr().out)['dry_run'] is True
    with SessionLocal() as db:
        assert count(db, Movie) == 0
    assert ingest_movies.main(['import', str(path), '--strict']) == 0
    assert json.loads(capsys.readouterr().out)['inserted'] == 1
    path.write_text(HEADER + 'Q999999992,Other,2001,,\nbad,Invalid,2000,,\n', encoding='utf-8')
    assert ingest_movies.main(['import', str(path), '--strict']) == 1
    assert 'strict import aborted' in capsys.readouterr().err
    with SessionLocal() as db:
        assert count(db, Movie) == 1
