"""Catalog search contract, including the title-versus-synopsis regression."""
import pytest
from app.db import SessionLocal
from app.catalog import set_movie_genres
from app.models import Movie, MovieCredit, Person, Rating, User

@pytest.fixture
def catalog():
    with SessionLocal() as db:
        data = [
            ('Up', 2009, 'Adventure, Comedy', 'An unexpected twist in the skies'),
            ('Twinkle', 2025, 'Drama', 'A quiet evening'),
            ('Twinkle Again', 2020, 'Drama, Romance', 'A second chance'),
            ('A Twinkle', 2019, 'Crime Drama', 'A mystery'),
            ('Twinkle Little Star', 2025, 'Drama, Science Fiction', 'Starlight and hope'),
            ('100% Real_Deal!', 2000, 'Documentary', 'A true story'),
            ('1000 RealXDeal', 2000, 'Comedy', 'Fiction')]
        for title,year,genres,synopsis in data:
            m=Movie(title=title,year=year,synopsis=synopsis)
            set_movie_genres(db,m,genres);db.add(m)
        db.flush()
        a=Person(name='Alex Smith');b=Person(name='Jamie Smith');db.add_all([a,b]);db.flush()
        db.add_all([MovieCredit(movie_id=1,person_id=a.id,role='actor',character='Carl'),
                    MovieCredit(movie_id=1,person_id=a.id,role='actor',character='Narrator'),
                    MovieCredit(movie_id=2,person_id=a.id,role='director'),
                    MovieCredit(movie_id=3,person_id=b.id,role='actor',character='Jo')])
        for i in range(2): db.add(User(username=f'user{i}',email=f'u{i}@example.org',password_hash='unused'))
        db.flush()
        db.add_all([Rating(movie_id=1,user_id=1,score=10),Rating(movie_id=1,user_id=2,score=8),Rating(movie_id=2,user_id=1,score=7),Rating(movie_id=3,user_id=1,score=9)])
        db.commit()

def result(client, **params):
    r=client.get('/api/movies',params=params);assert r.status_code==200,r.text;return r.json()

def titles(client, **params): return [m['title'] for m in result(client,**params)['items']]

def test_title_default_regression(client,catalog):
    assert titles(client,q='twi')==['Twinkle','Twinkle Again','Twinkle Little Star','A Twinkle']
    assert titles(client,q='twi',mode='synopsis')==['Up']
    assert 'Up' in titles(client,q='twi',mode='all')

def test_relevance_and_explicit_sort(client,catalog):
    assert titles(client,q='TWINKLE')==['Twinkle','Twinkle Again','Twinkle Little Star','A Twinkle']
    assert titles(client,q='twinkle',sort='title')[0]=='A Twinkle'
    assert titles(client,q='  little   twinkle ')==['Twinkle Little Star']

def test_literal_wildcards(client,catalog):
    for q in ('100%','Real_Deal','Deal!'):
        assert titles(client,q=q)==['100% Real_Deal!']
    assert titles(client,q='\\')==[]

def test_role_specific_search_no_duplicates(client,catalog):
    assert titles(client,q='Alex Smith',mode='actor')==['Up']
    assert titles(client,q='Alex Smith',mode='director')==['Twinkle']
    assert result(client,q='smith',mode='actor')['total']==2
    assert set(titles(client,q='smith',mode='all'))=={'Up','Twinkle','Twinkle Again'}
    assert titles(client,q='Alex quiet',mode='all')==['Twinkle']

def test_genre_modes_and_aliases(client,catalog):
    assert titles(client,genres=['drama film','Sci-Fi'])==['Twinkle Little Star']
    assert set(titles(client,genres=['drama','Adventure'],genre_mode='or'))=={'Up','Twinkle','Twinkle Again','Twinkle Little Star'}
    assert set(titles(client,genre='Drama',genres=['drama film']))=={'Twinkle','Twinkle Again','Twinkle Little Star'}

def test_combined_filters(client,catalog):
    assert titles(client,q='twinkle',genre='Drama',year_min=2020,year_max=2025,rating_min=8,rating_max=10)==['Twinkle Again']
    assert titles(client,year=2025)==['Twinkle','Twinkle Little Star']
    assert titles(client,rating_max=7)==['Twinkle']

def test_rating_sorts_unrated_last_and_summary(client,catalog):
    data=result(client,sort='rating')['items']
    assert [m['title'] for m in data[:3]]==['Up','Twinkle Again','Twinkle']
    assert (data[0]['average_rating'],data[0]['rating_count'])==(9.0,2)
    assert all(m['average_rating'] is None and m['rating_count']==0 for m in data[3:])
    assert titles(client,sort='most_rated')[0]=='Up'

def test_pagination_stable(client,catalog):
    all_ids=[x['id'] for x in result(client,sort='newest')['items']]
    pages=[result(client,sort='newest',size=2,page=n) for n in range(1,5)]
    assert all(x['total']==7 for x in pages)
    assert [x['id'] for p in pages for x in p['items']]==all_ids
    assert result(client,sort='newest',size=2,page=5)['items']==[]

@pytest.mark.parametrize('params',[{'mode':'unknown'},{'sort':'unknown'},{'genre_mode':'xor'},{'rating_min':9,'rating_max':3},{'year_min':2020,'year_max':2000},{'rating_min':0},{'year_min':1800},{'q':'x'*201},{'genres':['x']*21},{'q':'\x00'}])
def test_invalid_search_parameters(client,params):
    assert client.get('/api/movies',params=params).status_code==422
