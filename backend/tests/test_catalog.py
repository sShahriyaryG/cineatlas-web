"""Regression coverage for relational catalog data and the additive upgrade."""
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text, inspect, func
from sqlalchemy.exc import IntegrityError
from app.db import SessionLocal
from app.catalog import set_movie_genres
from app.ingestion import ingest
from app.models import Movie, Genre, MovieGenre, MovieCredit, Person, User
from test_api import headers, seed


def admin(client):
    h = headers(client, 'catalog_admin', 'catalog_admin@example.org')
    with SessionLocal() as db:
        db.scalar(select(User).where(User.username == 'catalog_admin')).role = 'admin'
        db.commit()
    return h


def test_exact_filter_canonical_alias_and_shared_genres(client):
    h = admin(client)
    for title, genres in [('Alpha', 'Sci-Fi, science fiction film, DRAMA, drama film'), ('Beta', 'Drama, Crime Drama'), ('Gamma', 'Crime Drama')]:
        assert client.post('/api/movies', headers=h, json=dict(title=title, year=2000, genres=genres)).status_code == 201
    assert client.get('/api/genres').json() == ['Crime Drama', 'Drama', 'Science Fiction']
    for alias in ['Sci-Fi', 'science fiction film', 'SCIENCE FICTION']:
        assert client.get('/api/movies', params={'genre':alias}).json()['total'] == 1
    assert client.get('/api/movies', params={'genre':'Drama'}).json()['total'] == 2
    assert client.get('/api/movies', params={'genre':'%'}).json()['total'] == 0
    assert client.get('/api/movies/1').json()['genres'] == ['Drama', 'Science Fiction']
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Genre)) == 3
        assert db.scalar(select(func.count()).select_from(MovieGenre)) == 5


def test_edit_replaces_links_and_clear_updates_public_filter(client):
    seed(); h = admin(client)
    payload = dict(title='Orbit', year=2020, genres='Comedy, comedy film')
    assert client.put('/api/movies/1', headers=h, json=payload).json()['genres'] == ['Comedy']
    assert client.get('/api/movies', params={'genre':'Sci-Fi'}).json()['total'] == 0
    assert client.put('/api/movies/1', headers=h, json={**payload, 'genres':''}).json()['genres'] == []
    assert 'Comedy' not in client.get('/api/genres').json()
    assert client.get('/api/movies/2').json()['genres'] == ['Drama','Romance']


def test_long_genre_list_kept_in_links_and_validated(client):
    h = admin(client)
    names = [f'Genre {i:02d} example longer label' for i in range(20)]
    payload = dict(title='Many genres',year=2000,genres=','.join(names))
    r = client.post('/api/movies', headers=h, json=payload)
    assert r.status_code == 201, r.text
    assert len(r.json()['genres']) == len(names)
    with SessionLocal() as db:
        assert len(db.get(Movie,r.json()['id']).genres) <= 255
    assert client.put('/api/movies/1', headers=h, json={**payload,'genres':', '.join(r.json()['genres'])}).status_code == 200
    assert client.post('/api/movies', headers=h, json={**payload,'genres':'x'*513}).status_code == 422


def test_import_no_longer_discards_labels_over_255():
    names = [f'Genre {i:02d} sample longer label' for i in range(20)]
    csv = 'film,title,year,genres,runtime\nQ123456789,Movie,2000,'+'|'.join(names)+',99\n'
    with SessionLocal() as db:
        assert ingest(db, io.StringIO(csv), strict=True).inserted == 1
        db.commit()
        assert len(db.scalar(select(Movie)).genre_entries) == 20


def test_recommendation_matches_canonical_genre(client):
    h = admin(client)
    for title, g in [('Seed','science fiction film'), ('Alpha','Drama'), ('Beta','Sci-Fi')]:
        assert client.post('/api/movies',headers=h,json=dict(title=title,year=2001,genres=g)).status_code == 201
    member = headers(client, 'viewer', 'viewer@example.org')
    assert client.put('/api/movies/1/rating',headers=member,json={'score':9}).status_code == 200
    assert client.get('/api/me/recommendations',headers=member).json()[0]['title'] == 'Beta'


def test_people_credits_permissions_and_cleanup(client):
    seed(); h = admin(client); member = headers(client,'viewer','viewer@example.org')
    data={'name':'  Fictional Person  ','biography':'An example biography.'}
    assert client.post('/api/persons',headers=member,json=data).status_code == 403
    p = client.post('/api/persons',headers=h,json=data)
    assert p.status_code == 201 and p.json()['name'] == 'Fictional Person'
    pid = p.json()['id']
    # Names are not external identities; two different people may share a name.
    assert client.post('/api/persons',headers=h,json=data).json()['id'] != pid
    assert client.get('/api/persons',params={'q':'fictional'}).json()['total'] == 2
    assert client.put(f'/api/persons/{pid}',headers=member,json=data).status_code == 403
    assert client.put(f'/api/persons/{pid}',headers=h,json={**data,'biography':'Updated'}).json()['biography'] == 'Updated'
    path = '/api/movies/1/credits'; credit = {'person_id':pid,'role':'actor','character':'Captain'}
    assert client.post(path,headers=member,json=credit).status_code == 403
    assert client.post(path,headers=h,json={**credit,'person_id':999}).status_code == 404
    assert client.post(path,headers=h,json={**credit,'role':'director'}).status_code == 422
    r = client.post(path,headers=h,json=credit)
    assert r.status_code == 201, r.text
    cid = r.json()['id']
    assert client.post(path,headers=h,json=credit).status_code == 409
    assert client.post(path,headers=h,json={**credit,'role':'director','character':''}).status_code == 201
    assert client.post('/api/movies/2/credits',headers=h,json=credit).status_code == 201
    assert len(client.get(path).json()) == 2
    assert len(client.get(f'/api/persons/{pid}').json()['credits']) == 3
    assert client.delete(f'{path}/{cid}',headers=member).status_code == 403
    assert client.delete(f'/api/movies/2/credits/{cid}',headers=h).status_code == 404
    assert client.delete(f'{path}/{cid}',headers=h).status_code == 204
    assert client.delete('/api/movies/1',headers=h).status_code == 204
    assert client.get(path).status_code == 404
    assert len(client.get(f'/api/persons/{pid}').json()['credits']) == 1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(MovieCredit)) == 1
        assert db.scalar(select(func.count()).select_from(MovieGenre).where(MovieGenre.movie_id==1)) == 0
        assert db.get(Person,pid) is not None


def test_migration_backfills_and_preserves_existing_records(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    url = f'sqlite:///{tmp_path / "prior.db"}'
    engine = create_engine(url)
    env = dict(os.environ,DATABASE_URL=url)
    def migrate(direction, revision):
        subprocess.run([sys.executable,'-m','alembic',direction,revision],cwd=backend,env=env,check=True,capture_output=True)
    migrate('upgrade','0002_movie_sources')
    assert 'genres' not in inspect(engine).get_table_names()
    with engine.begin() as db:
        db.execute(text("INSERT INTO movies (id,title,year,genres,synopsis,poster_url,language,country) VALUES (41,'Original',2000,' Sci-Fi,DRAMA,drama film ','Manual edit','','',''),(42,'Empty',2001,'','','','','')"))
        db.execute(text("INSERT INTO users (id,username,email,password_hash,role,bio,is_active,created_at) VALUES (5,'old','old@example.org','test','member','',1,CURRENT_TIMESTAMP)"))
        db.execute(text("INSERT INTO ratings (id,user_id,movie_id,score) VALUES (1,5,41,8)"))
        db.execute(text("INSERT INTO reviews (id,user_id,movie_id,title,body,spoiler,hidden,created_at) VALUES (1,5,41,'Test','Review',0,0,CURRENT_TIMESTAMP)"))
        db.execute(text("INSERT INTO watchlist (id,user_id,movie_id) VALUES (1,5,41)"))
        db.execute(text("INSERT INTO movie_sources (source,external_id,movie_id,imported_at) VALUES ('wikidata','Q42',41,CURRENT_TIMESTAMP)"))
    migrate('upgrade','head')
    with engine.connect() as db:
        assert db.execute(text('SELECT g.name FROM genres g JOIN movie_genres mg ON g.id=mg.genre_id WHERE mg.movie_id=41 ORDER BY g.name')).scalars().all() == ['Drama','Science Fiction']
        assert db.scalar(text('SELECT count(*) FROM movie_genres WHERE movie_id=42')) == 0
        assert db.scalar(text('SELECT synopsis FROM movies WHERE id=41')) == 'Manual edit'
        assert db.scalar(text('SELECT score FROM ratings WHERE movie_id=41')) == 8
        for table in ('users','reviews','watchlist','movie_sources'):
            assert db.scalar(text(f'SELECT count(*) FROM {table}')) == 1
    migrate('downgrade','0002_movie_sources')
    with engine.connect() as db:
        assert db.scalar(text('SELECT genres FROM movies WHERE id=41')) == ' Sci-Fi,DRAMA,drama film '
    migrate('upgrade','head')
    with engine.connect() as db:
        assert db.scalar(text('SELECT count(*) FROM movie_genres')) == 2
    engine.dispose()


def test_strict_import_rolls_back_genres_too():
    csv = 'film,title,year,genres,runtime\nQ123,Valid,2000,Drama,100\nbad,Invalid,2001,Action,90\n'
    with pytest.raises(ValueError, match='strict import aborted'):
        with SessionLocal() as db:
            ingest(db, io.StringIO(csv), strict=True)
            db.commit()
    with SessionLocal() as db:
        for model in (Movie, Genre, MovieGenre):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_legacy_import_creates_relationships_and_no_duplicates(tmp_path):
    import csv
    import zipfile
    from import_legacy import import_movies
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=['uuid','release_date','title','genres'])
    writer.writeheader()
    writer.writerow(dict(uuid='legacy-fixture',release_date='2001-01-01',title='Legacy title',genres='["Sci-Fi", "Drama", "drama film"]'))
    path = tmp_path / 'fixture.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('db_data/movies.csv', stream.getvalue())
    import_movies(path)
    import_movies(path)
    with SessionLocal() as db:
        movie = db.scalar(select(Movie))
        assert [g.name for g in movie.genre_entries] == ['Drama','Science Fiction']
        assert db.scalar(select(func.count()).select_from(MovieGenre)) == 2
        assert db.scalar(select(func.count()).select_from(Movie)) == 1


def test_database_credit_and_link_constraints():
    seed()
    with SessionLocal() as db:
        person = Person(name='Fixture')
        db.add(person); db.commit()
        mid = db.scalar(select(Movie.id))
        pid = person.id
        gid = db.scalar(select(MovieGenre.genre_id).where(MovieGenre.movie_id==mid))
        db.add(MovieGenre(movie_id=mid,genre_id=gid))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(MovieCredit(movie_id=mid,person_id=pid,role='invalid',character=''))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(MovieCredit(movie_id=mid,person_id=pid,role='director',character='Invalid'))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
