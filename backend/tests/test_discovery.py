"""Read-only discovery endpoints stay public and return real catalog credits."""
from app.db import SessionLocal
from app.models import Movie, MovieCredit, Person
from test_api import seed


def test_person_filmography_contains_movie_posters_and_all_roles(client):
    seed()
    with SessionLocal() as db:
        person = Person(name='Example Person', biography='Example bio')
        db.add(person); db.flush()
        pid = person.id
        db.get(Movie, 1).poster_url = 'https://example.org/poster.jpg'
        db.add_all([MovieCredit(movie_id=1, person_id=pid, role='actor', character='Pilot'),
                    MovieCredit(movie_id=1, person_id=pid, role='director', character=''),
                    MovieCredit(movie_id=2, person_id=pid, role='writer', character='')])
        db.commit()
    result = client.get(f'/api/persons/{pid}')
    assert result.status_code == 200
    data = result.json()
    assert data['name'] == 'Example Person' and data['biography'] == 'Example bio'
    assert [c['movie_id'] for c in data['credits']] == [2, 1, 1]
    assert data['credits'][0]['poster_url'] == ''
    assert data['credits'][1]['poster_url'] == data['credits'][2]['poster_url'] == 'https://example.org/poster.jpg'
    assert {c['role'] for c in data['credits']} == {'actor','director','writer'}
    assert next(c for c in data['credits'] if c['role']=='actor')['character'] == 'Pilot'
    for credit in data['credits']:
        assert client.get(f'/api/movies/{credit["movie_id"]}').status_code == 200
    assert {c['person_id'] for c in client.get('/api/movies/1/credits').json()} == {pid}


def test_missing_and_empty_detail_records(client):
    with SessionLocal() as db:
        person = Person(name='No Credits Yet')
        db.add(person); db.commit(); pid = person.id
    assert client.get(f'/api/persons/{pid}').json()['credits'] == []
    assert client.get('/api/persons/9999').status_code == 404
    assert client.get('/api/movies/9999').status_code == 404
    assert client.get('/api/movies/9999/credits').status_code == 404
