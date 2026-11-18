from test_api import headers, seed

def test_ratings_require_login_and_start_empty(client):
    seed()
    assert client.get('/api/me/ratings').status_code == 401
    h = headers(client)
    response = client.get('/api/me/ratings', headers=h)
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers['cache-control'] == 'no-store'

def test_ratings_are_private_and_separate_from_community_scores(client):
    seed()
    a = headers(client, 'alice', 'alice@example.org')
    b = headers(client, 'bobby', 'bobby@example.org')
    for h, movie_id, score in [(a, 1, 9), (a, 2, 7), (b, 1, 3)]:
        assert client.put(f'/api/movies/{movie_id}/rating', headers=h, json={'score':score}).status_code == 200
    r = client.get('/api/me/ratings', headers=a).json()
    assert [(m['id'], m['my_score']) for m in r] == [(1,9),(2,7)]
    assert r[0]['average_rating'] == 6 and r[0]['rating_count'] == 2
    assert r[0]['genres'] == ['Drama','Science Fiction']
    assert [(m['id'], m['my_score']) for m in client.get('/api/me/ratings', headers=b).json()] == [(1,3)]
    assert 'my_score' not in client.get('/api/movies/1').json()

def test_rating_update_changes_one_record_and_logout_revokes_access(client):
    seed(); h = headers(client)
    for score in (8, 4):
        assert client.put('/api/movies/2/rating', headers=h, json={'score':score}).status_code == 200
    assert client.put('/api/me/watchlist/1', headers=h).status_code == 200
    assert [(m['id'],m['my_score']) for m in client.get('/api/me/ratings', headers=h).json()] == [(2,4)]
    assert client.post('/api/auth/logout', headers=h).status_code == 204
    assert client.get('/api/me/ratings', headers=h).status_code == 401
