"""Directory queries count local films, preserve identity and paginate predictably."""
from app.db import SessionLocal
from app.models import Person, PersonMetadata, PersonAlternativeName, MovieCredit, Movie, Language, Country, Tag
from app.metadata import apply_movie_metadata, MovieMetadataPatch
from test_api import seed


def test_people_search_roles_portraits_and_pagination(client):
    seed()
    with SessionLocal() as db:
        a=Person(name='Amy Example'); b=Person(name='Zed Example'); c=Person(name='No credits')
        db.add_all([a,b,c]); db.flush(); aid,bid,cid=a.id,b.id,c.id
        db.add_all([PersonMetadata(person_id=aid,profile_url='https://example.org/amy.jpg'),
                    PersonAlternativeName(person_id=aid,key='stage alias',name='Stage Alias'),
                    MovieCredit(movie_id=1,person_id=aid,role='actor',character='Pilot'),
                    MovieCredit(movie_id=1,person_id=aid,role='director',character=''),
                    MovieCredit(movie_id=2,person_id=aid,role='actor',character='Hero'),
                    MovieCredit(movie_id=2,person_id=bid,role='composer',character='')]); db.commit()
    path='/api/directory/people'
    r=client.get(path,params={'size':1}).json(); assert r['total']==3 and r['items'][0]['id']==aid
    assert r['items'][0]['film_count']==2 and r['items'][0]['roles']==['actor','director']
    assert r['items'][0]['profile_url']=='https://example.org/amy.jpg'
    assert client.get(path,params={'page':2,'size':1}).json()['items'][0]['id']==cid
    assert client.get(path,params={'page':3,'size':1}).json()['items'][0]['id']==bid
    assert client.get(path,params={'q':'stage alias','role':'director'}).json()['total']==1
    assert client.get(path,params={'q':'stage alias','role':'composer'}).json()['total']==0
    assert client.get(path,params={'q':'%'}).json()['total']==0
    assert client.get(path,params={'role':'unknown'}).status_code==422
    assert client.get(path,params={'size':51}).status_code==422
    assert client.get(path,params={'q':'x\x00'}).status_code==422
    assert client.get('/api/persons').json()['total']==3  # existing endpoint unchanged
    credits=client.get('/api/movies/1/credits').json()
    assert len(credits)==2 and all(x['profile_url']=='https://example.org/amy.jpg' for x in credits)
    assert client.get('/api/movies/2/credits').json()[1]['profile_url'] is None


def test_classification_lists_and_movie_links(client):
    seed()
    with SessionLocal() as db:
        apply_movie_metadata(db,db.get(Movie,1),MovieMetadataPatch(original_language='English',spoken_languages=['English','French'],production_countries=['France'],tags=['Space']))
        apply_movie_metadata(db,db.get(Movie,2),MovieMetadataPatch(spoken_languages=['English'],production_countries=['Canada'],tags=['Space','Family']))
        db.add(Language(key='unused',name='Unused'));db.add(Country(key='another',name='Another'));db.add(Tag(key='orphan',name='Orphan'));db.commit()
    path='/api/directory/classifications'
    data=client.get('/api/movies/1/metadata').json()['classifications']
    english=[l for l in data['languages'] if l['name']=='English']
    assert len(english)==2 and english[0]['id']==english[1]['id']
    assert {l['kind'] for l in english}=={'original','spoken'}
    for category,name,n in [('genres','Drama',2),('languages','English',2),('countries','France',1),('tags','Space',2)]:
        result=client.get(f'{path}/{category}',params={'q':name}).json();assert result['total']==1
        link=result['items'][0];assert link['film_count']==n and link['name']==name
        assert link['id'] in {x['id'] for x in data[category]}
        detail=client.get(f'{path}/{category}/{link["id"]}',params={'size':1}).json()
        assert detail['classification']=={'id':link['id'],'name':name} and detail['total']==n
        assert detail['items'][0]['id']==1 and detail['items'][0]['rating_count']==0
        if n==2:
            assert client.get(f'{path}/{category}/{link["id"]}',params={'size':1,'page':2}).json()['items'][0]['id']==2
    assert client.get(path+'/languages').json()['total']==2
    assert client.get(path+'/countries').json()['total']==2
    assert client.get(path+'/tags').json()['total']==2
    assert client.get(path+'/tags',params={'q':'%'}).json()['total']==0
    assert client.get(path+'/tags',params={'size':1,'page':2}).json()['items'][0]['name']=='Space'


def test_directory_empty_missing_and_validation(client):
    assert client.get('/api/directory/people').json()['items']==[]
    assert client.get('/api/directory/classifications/tags').json()['total']==0
    with SessionLocal() as db:
        tag=Tag(name='Unused',key='unused');db.add(tag);db.commit();tid=tag.id
    r=client.get(f'/api/directory/classifications/tags/{tid}');assert r.status_code==200 and r.json()['total']==0
    assert client.get('/api/directory/classifications/tags/98765').status_code==404
    assert client.get('/api/directory/classifications/tags/2147483648').status_code==404
    assert client.get('/api/directory/classifications/people').status_code==422
    assert client.get('/api/directory/classifications/tags',params={'page':0}).status_code==422
    assert client.get('/api/directory/classifications/tags',params={'q':'x\x00'}).status_code==422


def test_shared_search_and_vocabulary_filters(client):
    seed()
    with SessionLocal() as db:
        apply_movie_metadata(db,db.get(Movie,1),MovieMetadataPatch(original_language='English',spoken_languages=['English','French'],production_countries=['France'],tags=['Space']))
        apply_movie_metadata(db,db.get(Movie,2),MovieMetadataPatch(spoken_languages=['English'],production_countries=['Canada'],tags=['Family']))
        db.add(Country(name='Unused',key='unused'));db.commit()
    r=client.get('/api/directory/filter-options')
    assert r.status_code==200
    options={k:{x['name']:x['id'] for x in v} for k,v in r.json().items()}
    assert set(options['countries'])=={'France','Canada'}
    assert set(options['languages'])=={'English','French'}
    english,french=options['languages']['English'],options['languages']['French']
    france,canada=options['countries']['France'],options['countries']['Canada']
    space,family=options['tags']['Space'],options['tags']['Family']
    drama=options['genres']['Drama']
    path='/api/movies'; scoped=f'/api/directory/classifications/countries/{france}'
    def ids(url,params):
        reply=client.get(url,params=params);assert reply.status_code==200,reply.text
        data=reply.json();assert data['total']==len(data['items']);return [m['id'] for m in data['items']]
    assert ids(path,{'language_ids':[english]})==[1,2]
    assert ids(path,{'language_ids':[english,french]})==[1]
    assert ids(path,{'language_ids':[english,french],'language_mode':'or'})==[1,2]
    assert ids(path,{'country_ids':[france,canada]})==[]
    assert ids(path,{'country_ids':[france,canada],'country_mode':'or','tag_ids':[space]})==[1]
    assert ids(path,{'tag_ids':[space,family],'tag_mode':'or','language_ids':[french]})==[1]
    assert ids(path,{'tag_ids':[space,family]})==[]
    assert ids(scoped,{'country_ids':[france,canada],'country_mode':'or'})==[1]
    assert ids(scoped,{'country_ids':[canada]})==[]
    assert ids(scoped,{'tag_ids':[family]})==[]
    assert ids(scoped,{'q':'x-no-match'})==[]
    title=client.get('/api/movies/1').json()['title']
    assert ids(scoped,{'q':title,'mode':'title','language_ids':[english],'genres':['Drama']})==[1]
    assert ids(f'/api/directory/classifications/genres/{drama}',{'country_ids':[canada]})==[2]
    for url in (path,scoped):
        for params in ({'language_ids':0},{'country_ids':2147483648},{'tag_ids':[space]*21},{'tag_mode':'xor'},{'rating_min':9,'rating_max':2}):
            assert client.get(url,params=params).status_code==422
