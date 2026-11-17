from app.db import SessionLocal
from app.models import Movie,User
from app.catalog import set_movie_genres
from app.security import hash_password

def headers(c,username='sara',email='sara@example.org'):
    r=c.post('/api/auth/register',json={'username':username,'email':email,'password':'complex-password-123'})
    assert r.status_code==201,r.text
    return {'Authorization':'Bearer '+r.json()['token']}
def seed():
    with SessionLocal() as db:
        for title,year,genres,synopsis in [('Orbit',2020,'Sci-Fi,Drama','A journey through space'),('Summer Light',2021,'Drama,Romance','A story of friendship')]:
            movie=Movie(title=title,year=year,synopsis=synopsis)
            set_movie_genres(db,movie,genres);db.add(movie)
        db.commit()

def test_catalog_filters_and_details(client):
    seed();r=client.get('/api/movies',params={'q':'Orbit'});assert r.status_code==200;assert r.json()['total']==1
    assert client.get('/api/movies',params={'genre':'Sci-Fi'}).json()['total']==1
    assert client.get('/api/movies/999').status_code==404
    assert client.get('/api/genres').json()==['Drama','Romance','Science Fiction']
def test_auth_validation_and_permissions(client):
    h=headers(client)
    assert client.post('/api/auth/register',json={'username':'sara','email':'other@example.com','password':'complex-password-123'}).status_code==409
    assert client.post('/api/auth/login',json={'identifier':'sara','password':'wrong'}).status_code==401
    assert client.post('/api/movies',headers=h,json={'title':'Test','year':2020,'genres':'Drama'}).status_code==403
    assert client.get('/api/me/watchlist').status_code==401
    assert client.post('/api/auth/logout',headers=h).status_code==204
    assert client.get('/api/auth/me',headers=h).status_code==401

def test_rating_watchlist_review_recommendations(client):
    seed();h=headers(client)
    assert client.put('/api/movies/1/rating',json={'score':11},headers=h).status_code==422
    assert client.put('/api/movies/1/rating',json={'score':9},headers=h).json()['average_rating']==9.0
    assert client.put('/api/movies/1/rating',json={'score':7},headers=h).json()['rating_count']==1
    assert client.put('/api/me/watchlist/1',headers=h).status_code==200
    assert len(client.get('/api/me/watchlist',headers=h).json())==1
    assert client.delete('/api/me/watchlist/1',headers=h).json()['saved'] is False
    r=client.post('/api/movies/1/reviews',json={'title':'Enjoyed it','body':'Good film','spoiler':False},headers=h)
    assert r.status_code==201
    assert len(client.get('/api/movies/1/reviews').json())==1
    assert client.post('/api/reviews/1/reports',headers=h,json={'reason':'Inappropriate content'}).status_code==201
    assert client.get('/api/me/recommendations',headers=h).json()[0]['id']==2

def test_editor_admin_workflow(client):
    seed();editor=headers(client,'editor','editor@example.org');admin=headers(client,'admin','admin@example.org')
    with SessionLocal() as db:
        for name,role in [('editor','editor'),('admin','admin')]:
            u=db.query(User).filter_by(username=name).one();u.role=role
        db.commit()
    s=client.post('/api/movies/1/suggestions',headers=editor,json={'synopsis':'A newly updated story','reason':'Original was incomplete'})
    assert s.status_code==201
    assert client.post('/api/admin/suggestions/1/approved',headers=editor).status_code==403
    assert client.post('/api/admin/suggestions/1/approved',headers=admin).json()['status']=='approved'
    assert client.get('/api/movies/1').json()['synopsis']=='A newly updated story'
    assert client.post('/api/admin/suggestions/1/approved',headers=admin).status_code==409
    assert client.get('/api/admin/stats',headers=admin).json()['movies']==2

def test_admin_catalog_ui_api_and_editor_roles(client):
    member = headers(client, 'member1', 'member1@example.org')
    admin = headers(client, 'siteadmin', 'siteadmin@example.org')
    with SessionLocal() as db:
        db.query(User).filter_by(username='siteadmin').one().role = 'admin'
        db.commit()
    assert client.get('/api/admin/users', headers=member).status_code == 403
    users = client.get('/api/admin/users', headers=admin).json()
    member_id = next(u['id'] for u in users if u['username'] == 'member1')
    admin_id = next(u['id'] for u in users if u['username'] == 'siteadmin')
    assert client.patch(f'/api/admin/users/{admin_id}/role', headers=admin, json={'role': 'member'}).status_code == 409
    assert client.patch(f'/api/admin/users/{member_id}/role', headers=member, json={'role': 'editor'}).status_code == 403
    assert client.patch(f'/api/admin/users/{member_id}/role', headers=admin, json={'role': 'admin'}).status_code == 422
    assert client.patch(f'/api/admin/users/{member_id}/role', headers=admin, json={'role': 'editor'}).json()['role'] == 'editor'
    data = {'title':'New Film','year':2024,'genres':'Drama,Comedy','synopsis':'A first draft','poster_url':'','runtime':96,'language':'English','country':'UK'}
    r = client.post('/api/movies', headers=admin, json=data)
    assert r.status_code == 201, r.text
    movie_id = r.json()['id']
    assert client.post('/api/movies', headers=member, json=data).status_code == 403
    r = client.put(f'/api/movies/{movie_id}', headers=admin, json={**data,'synopsis':'Updated by admin'})
    assert r.status_code == 200 and r.json()['synopsis'] == 'Updated by admin'
    r = client.post(f'/api/movies/{movie_id}/suggestions', headers=member, json={'synopsis':'An improved description','reason':'Add more context'})
    assert r.status_code == 201, r.text
    assert client.get('/api/me/suggestions', headers=member).json()[0]['movie_title'] == 'New Film'
    assert client.get('/api/admin/suggestions', headers=member).status_code == 403
    assert client.post('/api/admin/suggestions/1/approved', headers=admin).status_code == 200
    assert client.get('/api/me/suggestions', headers=member).json()[0]['status'] == 'approved'
    assert client.get(f'/api/movies/{movie_id}').json()['synopsis'] == 'An improved description'
    assert client.delete(f'/api/movies/{movie_id}', headers=admin).status_code == 204
    assert client.get(f'/api/movies/{movie_id}').status_code == 404


def test_moderation_panel_api(client):
    seed()
    member = headers(client, 'reviewer', 'reviewer@example.org')
    admin = headers(client, 'moderator', 'moderator@example.org')
    with SessionLocal() as db:
        db.query(User).filter_by(username='moderator').one().role='admin'
        db.commit()
    r = client.post('/api/movies/1/reviews', headers=member, json={'title':'A review','body':'Some detailed feedback'})
    assert r.status_code==201
    review_id = r.json()['id']
    assert client.post(f'/api/reviews/{review_id}/reports', headers=member, json={'reason':'Potential spoiler'}).status_code==201
    reports = client.get('/api/admin/reports', headers=admin).json()
    assert reports[0]['review_id']==review_id
    assert client.post('/api/admin/reports/1/hidden', headers=member).status_code==403
    assert client.post('/api/admin/reports/1/hidden', headers=admin).status_code==200
    assert client.get('/api/movies/1/reviews').json()==[]


def test_review_report_submission_contract(client):
    seed()
    author = headers(client, 'author', 'author@example.org')
    reporter = headers(client, 'reporter', 'reporter@example.org')
    admin = headers(client, 'modadmin', 'modadmin@example.org')
    with SessionLocal() as db:
        db.query(User).filter_by(username='modadmin').one().role = 'admin'
        db.commit()
    review = client.post('/api/movies/1/reviews', headers=author, json={'title':'Test review','body':'Detailed review for testing.'})
    assert review.status_code == 201
    review_id = review.json()['id']
    path = f'/api/reviews/{review_id}/reports'
    assert client.post(path, json={'reason':'A legitimate reason'}).status_code == 401
    for invalid in ('    ', 'abc', 'x' * 1001):
        assert client.post(path, headers=reporter, json={'reason':invalid}).status_code == 422
    assert client.post('/api/reviews/99999/reports', headers=reporter, json={'reason':'Missing review'}).status_code == 404
    response = client.post(path, headers=reporter, json={'reason':'  Unmarked spoiler  '})
    assert response.status_code == 201, response.text
    report_id = response.json()['id']
    pending = client.get('/api/admin/reports', headers=admin).json()
    assert len(pending) == 1
    assert pending[0]['id'] == report_id
    assert pending[0]['reported_by'] == 'reporter'
    assert pending[0]['reason'] == 'Unmarked spoiler'
    assert pending[0]['status'] == 'pending'
    assert client.get('/api/movies/1/reviews').json()[0]['id'] == review_id
    assert client.post(f'/api/admin/reports/{report_id}/dismissed', headers=reporter).status_code == 403
    assert client.post(f'/api/admin/reports/{report_id}/dismissed', headers=admin).json()['status'] == 'dismissed'
    assert client.get('/api/movies/1/reviews').json()[0]['id'] == review_id
    assert client.post(f'/api/admin/reports/{report_id}/hidden', headers=admin).status_code == 409
