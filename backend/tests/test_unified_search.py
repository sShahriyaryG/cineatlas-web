from app.db import SessionLocal
from app.models import Movie, Person, MovieCredit, PersonAlternativeName, PersonMetadata
from app.metadata import apply_movie_metadata, MovieMetadataPatch
from test_api import seed


def setup():
    seed()
    with SessionLocal() as db:
        a=Person(name='Alex Example'); b=Person(name='Alex Example');db.add_all([a,b]);db.flush()
        ids=(a.id,b.id)
        db.add(PersonAlternativeName(person_id=a.id,key='stage alias',name='Stage Alias'))
        db.add(PersonMetadata(person_id=a.id,full_name='Alexander Example'))
        db.add_all([MovieCredit(movie_id=1,person_id=a.id,role='director'),MovieCredit(movie_id=1,person_id=b.id,role='actor'),MovieCredit(movie_id=2,person_id=a.id,role='actor')])
        m=db.get(Movie,1);m.runtime=120
        apply_movie_metadata(db,m,MovieMetadataPatch(original_title='Original Orbit',alternative_titles=['Galactic Voyage'],spoken_languages=['English','French'],production_countries=['France'],tags=['Space'],certifications=[{'country':'France','rating':'12'},{'country':'Canada','rating':'PG'}]))
        m=db.get(Movie,2);m.runtime=90
        apply_movie_metadata(db,m,MovieMetadataPatch(spoken_languages=['English'],production_countries=['Canada'],tags=['Family'],certifications=[{'country':'France','rating':'PG'},{'country':'Canada','rating':'12'}]))
        db.commit()
    return ids


def ids(client,params=None,path='/api/movies'):
    r=client.get(path,params=params);assert r.status_code==200,r.text
    return [m['id'] for m in r.json()['items']]


def test_aliases_and_search_context(client):
    a,b=setup()
    assert ids(client,{'q':'Galactic Voyage'})==[1]
    assert ids(client,{'q':'Original Orbit'})==[1]
    assert ids(client,{'q':'Stage Alias'})==[]
    assert ids(client,{'q':'Stage Alias','mode':'director'})==[1]
    for q in ('Stage Alias','Alexander Example','alias stage'):
        assert ids(client,{'q':q},'/api/directory/people')==[a]
    assert set(ids(client,{'q':'Alex Example'},'/api/directory/people'))=={a,b}


def test_include_exclude_and_fixed_scope(client):
    setup();options={k:{i['name']:i['id'] for i in v} for k,v in client.get('/api/directory/filter-options').json().items()}
    drama=options['genres']['Drama'];romance=options['genres']['Romance'];france=options['countries']['France'];canada=options['countries']['Canada'];english=options['languages']['English'];french=options['languages']['French'];space=options['tags']['Space'];family=options['tags']['Family']
    assert ids(client,{'genre_ids':[drama],'exclude_genre_ids':[romance],'language_ids':[english,french]})==[1]
    assert ids(client,{'language_ids':[english,french],'language_mode':'or','exclude_language_ids':[french]})==[2]
    assert ids(client,{'country_ids':[france,canada],'country_mode':'or','exclude_country_ids':[canada],'exclude_tag_ids':[family]})==[1]
    assert ids(client,{'tag_ids':[space,family],'tag_mode':'or','exclude_tag_ids':[space]})==[2]
    scope=f'/api/directory/classifications/countries/{france}'
    assert ids(client,{'tag_ids':[space],'exclude_genre_ids':[romance]},scope)==[1]
    assert ids(client,{'country_ids':[canada]},scope)==[]
    assert ids(client,{'exclude_country_ids':[france]},scope)==[]


def test_people_identity_role_and_runtime(client):
    a,b=setup()
    assert ids(client,{'credit':[f'{a}:director']})==[1]
    assert ids(client,{'credit':[f'{b}:actor']})==[1]
    assert ids(client,{'credit':[f'{a}:actor']})==[2]
    assert ids(client,{'credit':[f'{a}:director',f'{a}:actor']})==[]
    assert ids(client,{'credit':[f'{a}:director',f'{a}:actor'],'credit_mode':'or','exclude_credit':[f'{b}:any']})==[2]
    assert ids(client,{'credit':[f'{a}:any'],'runtime_min':100,'runtime_max':130})==[1]
    assert ids(client,{'runtime_max':100})==[2]


def test_certification_country_rating_pair(client):
    setup();options=client.get('/api/directory/certification-options').json()
    france=next(c['country_id'] for c in options if c['country']=='France')
    canada=next(c['country_id'] for c in options if c['country']=='Canada')
    assert ids(client,{'certification_country':france,'certification_rating':'12'})==[1]
    assert ids(client,{'certification_country':canada,'certification_rating':'12'})==[2]
    assert ids(client,{'certification_country':france})==[1,2]
    for params in ({'runtime_min':200,'runtime_max':10},{'runtime_min':0},{'certification_rating':'PG'},{'credit':'1:bad'},{'exclude_credit':'-1:any'},{'exclude_genre_ids':0},{'exclude_tag_ids':[1]*21}):
        assert client.get('/api/movies',params=params).status_code==422


def test_directory_sorting(client):
    a,b=setup()
    assert ids(client,{'sort':'count_desc'},'/api/directory/people')==[a,b]
    assert ids(client,{'sort':'count_asc'},'/api/directory/people')==[b,a]
    assert ids(client,{'sort':'title_desc'})==[2,1]
    r=client.get('/api/directory/classifications/genres',params={'sort':'count_desc'}).json()
    assert r['items'][0]['name']=='Drama' and r['items'][0]['film_count']==2
    assert client.get('/api/directory/people',params={'sort':'unknown'}).status_code==422


def test_global_search_groups_and_validation(client):
    a,b=setup()
    def search(q):
        r=client.get('/api/search',params={'q':q});assert r.status_code==200,r.text
        data=r.json();assert set(data)=={'films','people','genres','countries','languages','tags'}
        assert all(p['page']==1 and p['size']==5 for p in data.values())
        return data
    assert search('Galactic Voyage')['films']['items'][0]['id']==1
    alias=search('Stage Alias');assert alias['films']['total']==0 and alias['people']['items'][0]['id']==a
    assert search('Drama')['genres']['items'][0]['name']=='Drama'
    assert search('Science   Fiction')['genres']==client.get('/api/directory/classifications/genres',params={'q':'Science   Fiction','sort':'relevance','size':5}).json()
    assert search('France')['countries']['items'][0]['name']=='France'
    assert search('English')['languages']['items'][0]['name']=='English'
    assert search('Space')['tags']['items'][0]['name']=='Space'
    assert all(p['total']==0 for p in search('nothing-matches-123').values())
    for q in ('','   ','x\x00','x'*201):assert client.get('/api/search',params={'q':q}).status_code==422
