from app.db import SessionLocal
from app.models import Movie,User
from app.security import hash_password

def headers(c,username='sara',email='sara@example.org'):
    r=c.post('/api/auth/register',json={'username':username,'email':email,'password':'complex-password-123'})
    assert r.status_code==201,r.text
    return {'Authorization':'Bearer '+r.json()['token']}
def seed():
    with SessionLocal() as db:
        db.add_all([Movie(title='Orbit',year=2020,genres='Sci-Fi,Drama',synopsis='A journey through space'),Movie(title='Summer Light',year=2021,genres='Drama,Romance',synopsis='A story of friendship')]);db.commit()

def test_catalog_filters_and_details(client):
    seed();r=client.get('/api/movies',params={'q':'Orbit'});assert r.status_code==200;assert r.json()['total']==1
    assert client.get('/api/movies',params={'genre':'Sci-Fi'}).json()['total']==1
    assert client.get('/api/movies/999').status_code==404
    assert client.get('/api/genres').json()==['Drama','Romance','Sci-Fi']
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
