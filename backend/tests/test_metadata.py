"""Regression coverage for metadata extensions and legacy compatibility."""
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, select, func, text
from sqlalchemy.exc import IntegrityError
from app.db import SessionLocal
from app.models import (Movie, MovieLanguage, Language, Country, MovieCountry, MovieCredit,
                        Person, MovieMetadataOverride, PersonMetadataOverride)
from app.metadata import MOVIE_EXTENSION_MODELS
from test_api import headers, seed
from test_catalog import admin


def film(client, auth, **extra):
    r=client.post('/api/movies',headers=auth,json={'title':'Metadata fixture','year':2021,'genres':'Drama',**extra})
    assert r.status_code==201,r.text
    return r.json()['id']


def test_unknown_metadata_and_legacy_labels(client):
    h=admin(client)
    mid=film(client,h,language='English',country='Example, Republic of')
    path=f'/api/movies/{mid}/metadata'
    result=client.get(path).json()
    assert result['original_language'] is None and result['spoken_languages']==[]
    assert result['unspecified_languages']==['English']
    assert result['production_countries']==['Example, Republic of']
    assert result['release_date'] is None and result['certifications']==[]
    assert client.get(f'/api/movies/{mid}').json()['language']=='English'
    blank=film(client,h)
    result=client.get(f'/api/movies/{blank}/metadata').json()
    assert result['production_countries']==[] and result['unspecified_languages']==[]
    assert result['original_title'] is None
    assert client.get('/api/movies/99999/metadata').status_code==404
    assert client.get('/api/persons/99999/metadata').status_code==404


def test_movie_metadata_roundtrip_and_partial_updates(client):
    h=admin(client);mid=film(client,h,language='English',country='France')
    path=f'/api/movies/{mid}/metadata'
    payload={'original_title':'Original fixture','alternative_titles':['Alt A','alt a','Alternate title'],
             'release_date':'2021-05-02','release_status':'released','trailer_url':'https://example.org/trailer',
             'original_language':'English','spoken_languages':['English','French','french'],
             'production_countries':['France','Canada','france'],'tags':['Space','space','Adventure'],
             'certifications':[{'country':'Canada','rating':'PG'},{'country':'France','rating':'U'},{'country':'Canada','rating':'pg'}],
             'soundtracks':[{'title':'Synthetic track','artist':'Example artist'},{'title':'Second track','composer':'Test'}],
             'quotes':[{'quote':'Synthetic example quotation.','spoiler':True,'speaker':'Test'}]}
    r=client.patch(path,headers=h,json=payload);assert r.status_code==200,r.text
    m=r.json(); assert m['original_language']=='English' and m['spoken_languages']==['English','French']
    assert m['unspecified_languages']==[] and m['production_countries']==['Canada','France']
    assert m['alternative_titles']==['Alt A','Alternate title'] and len(m['certifications'])==2
    assert m['tags']==['Adventure','Space'] and m['quotes'][0]['spoiler'] is True
    assert [x['title'] for x in m['soundtracks']]==['Synthetic track','Second track']
    assert client.get(path).json()==m
    assert client.patch(path,headers=h,json=payload).json()==m
    r=client.patch(path,headers=h,json={'spoken_languages':['German'],'quotes':[],'trailer_url':None})
    assert r.status_code==200,r.text
    updated=r.json();assert updated['spoken_languages']==['German'] and updated['original_language']=='English'
    assert updated['quotes']==[] and updated['trailer_url'] is None and updated['tags']==m['tags']
    assert updated['certifications']==m['certifications'] and updated['soundtracks']==m['soundtracks']
    row=client.get(f'/api/movies/{mid}').json(); assert row['production_countries']==['Canada','France']
    assert row['language']=='English' and row['original_language']=='English'
    assert client.get('/api/movies',params={'q':'Metadata fixture'}).json()['items'][0]['original_language']=='English'
    assert client.patch(path,headers=h,json={'original_language':None,'spoken_languages':[],'unspecified_languages':[],'production_countries':[]}).status_code==200
    row=client.get(f'/api/movies/{mid}').json();assert row['language']=='' and row['country']==''
    assert row['production_countries']==[] and row['unspecified_languages']==[]
    with SessionLocal() as db:
        assert db.get(MovieMetadataOverride,(mid,'original_language')) is not None
        assert db.get(MovieMetadataOverride,(mid,'production_countries')) is not None


def test_legacy_update_does_not_destroy_richer_data(client):
    h=admin(client);mid=film(client,h,language='English',country='France')
    path=f'/api/movies/{mid}'
    base={'title':'Metadata fixture','year':2021,'genres':'Drama','language':'English','country':'France'}
    assert client.put(path,headers=h,json={**base,'language':'French'}).status_code==200
    assert client.get(path+'/metadata').json()['unspecified_languages']==['French']
    assert client.patch(path+'/metadata',headers=h,json={'original_language':'French','spoken_languages':['English'],'production_countries':['France','Italy']}).status_code==200
    base.update(language='French',country='France',synopsis='A revised synopsis')
    assert client.put(path,headers=h,json=base).status_code==200
    assert client.put(path,headers=h,json={**base,'language':'German'}).status_code==409
    assert client.put(path,headers=h,json={**base,'country':'Italy'}).status_code==409
    assert client.put(path,headers=h,json={'title':'Metadata fixture','year':2021,'genres':'Drama'}).status_code==200
    result=client.get(path+'/metadata').json()
    assert result['original_language']=='French' and result['production_countries']==['France','Italy']


def test_person_metadata_and_extended_credits(client):
    h=admin(client);mid=film(client,h)
    p=client.post('/api/persons',headers=h,json={'name':'Synthetic person','biography':'Fixture bio'}).json();pid=p['id']
    path=f'/api/persons/{pid}/metadata'
    values={'full_name':'Synthetic Full Name','alternative_names':['Alias','alias'],'profile_url':'https://example.org/person.jpg',
            'birthday':'1980-01-01','birthplace':'Example Town','nationalities':['France','Canada']}
    r=client.patch(path,headers=h,json=values);assert r.status_code==200,r.text
    record=r.json();assert record['alternative_names']==['Alias'] and record['nationalities']==['Canada','France']
    assert record['deathday'] is None and record['birthday']=='1980-01-01'
    assert client.patch(path,headers=h,json={'deathday':'1979-01-01','birthplace':'Other'}).status_code==422
    assert client.get(path).json()==record
    with SessionLocal() as db:
        assert db.get(PersonMetadataOverride,(pid,'deathday')) is None
    assert client.patch(path,headers=h,json={'birthday':None}).json()['birthday'] is None
    with SessionLocal() as db:
        assert db.get(PersonMetadataOverride,(pid,'birthday')) is not None
    assert client.put(f'/api/persons/{pid}',headers=h,json={'name':'Synthetic person','biography':'Edited'}).status_code==200
    assert client.get(path).json()['profile_url']==values['profile_url']
    assert client.get(f'/api/persons/{pid}').json()['biography']=='Edited'
    for role in ('composer','cinematographer','editor','other'):
        r=client.post(f'/api/movies/{mid}/credits',headers=h,json={'person_id':pid,'role':role});assert r.status_code==201,r.text
    assert {c['role'] for c in client.get(f'/api/persons/{pid}').json()['credits']}=={'composer','cinematographer','editor','other'}
    assert client.post(f'/api/movies/{mid}/credits',headers=h,json={'person_id':pid,'role':'composer','character':'Test'}).status_code==422


def test_metadata_permissions_validation_and_cleanup(client):
    h=admin(client);mid=film(client,h);member=headers(client,'viewer','viewer@example.org')
    person=client.post('/api/persons',headers=h,json={'name':'Fixture'}).json()['id']
    path=f'/api/movies/{mid}/metadata';pp=f'/api/persons/{person}/metadata'
    for p in (path,pp):
        assert client.patch(p,json={}).status_code==401
        assert client.patch(p,headers=member,json={}).status_code==403
    for invalid in ({'trailer_url':'javascript:alert(1)'},{'original_language':'   '},{'release_date':'2021-02-30'},
                    {'tags':['\x00']},{'unknown_field':'x'},{'certifications':[{'country':'France','rating':''}]},
                    {'soundtracks':[{'title':'Test','external_url':'https://user:pass@example.org'}]}):
        assert client.patch(path,headers=h,json=invalid).status_code==422,invalid
    assert client.patch(pp,headers=h,json={'birthday':'2200-01-01'}).status_code==422
    assert client.patch(path,headers=h,json={'original_title':'Test','original_language':'English','production_countries':['Canada'],'tags':['Tag'],'alternative_titles':['Alt'],'certifications':[{'country':'Canada','rating':'G'}],'soundtracks':[{'title':'Track'}],'quotes':[{'quote':'Test quote'}]}).status_code==200
    assert client.delete(f'/api/movies/{mid}',headers=h).status_code==204
    with SessionLocal() as db:
        for model in MOVIE_EXTENSION_MODELS:
            assert db.scalar(select(func.count()).select_from(model).where(model.movie_id==mid))==0,model.__name__
        assert db.scalar(select(func.count()).select_from(Country))==1


def test_one_original_language_db_constraint(client):
    h=admin(client);mid=film(client,h)
    with SessionLocal() as db:
        a=Language(name='A',key='a');b=Language(name='B',key='b');db.add_all([a,b]);db.flush()
        db.add_all([MovieLanguage(movie_id=mid,language_id=a.id,kind='original'),MovieLanguage(movie_id=mid,language_id=b.id,kind='original')])
        with pytest.raises(IntegrityError):db.commit()
        db.rollback()


def test_upgrade_backfills_legacy_and_preserves_existing_rows(tmp_path):
    url=f'sqlite:///{tmp_path / "before.db"}'
    engine=create_engine(url)
    backend=Path(__file__).resolve().parents[1]
    def migrate(direction,revision):
        result=subprocess.run([sys.executable,'-m','alembic',direction,revision],cwd=backend,env=dict(os.environ,DATABASE_URL=url),capture_output=True,text=True)
        assert result.returncode==0,result.stderr
    migrate('upgrade','0005_session_security')
    assert 'movie_metadata' not in inspect(engine).get_table_names()
    with engine.begin() as db:
        db.execute(text("INSERT INTO movies (id,title,year,genres,synopsis,poster_url,language,country) VALUES (99,'Legacy',2000,'Drama','Keep me','',' English ','France'),(100,'Legacy two',2000,'Drama','','','english','FRANCE'),(101,'Blank',2000,'Drama','','','','')"))
        db.execute(text("INSERT INTO persons (id,name,biography) VALUES (17,'Legacy person','Keep bio')"))
        db.execute(text("INSERT INTO movie_credits (id,movie_id,person_id,role,character) VALUES (5,99,17,'actor','Hero')"))
        db.execute(text("INSERT INTO users (id,username,email,password_hash,role,bio,is_active,created_at) VALUES (5,'old','old@example.org','hash','member','',1,CURRENT_TIMESTAMP)"))
        db.execute(text("INSERT INTO ratings (id,user_id,movie_id,score) VALUES (1,5,99,8)"))
        db.execute(text("INSERT INTO watchlist (id,user_id,movie_id) VALUES (1,5,99)"))
        db.execute(text("INSERT INTO movie_sources (source,external_id,movie_id,imported_at) VALUES ('wikidata','Q99',99,CURRENT_TIMESTAMP)"))
        db.execute(text("INSERT INTO person_sources (source,external_id,person_id) VALUES ('tmdb','17',17)"))
    migrate('upgrade','head');migrate('upgrade','head')
    with engine.connect() as db:
        assert db.scalar(text('SELECT language FROM movies WHERE id=99'))==' English '
        assert db.scalar(text('SELECT count(*) FROM languages'))==1
        assert db.scalar(text('SELECT count(*) FROM countries'))==1
        assert db.scalar(text("SELECT count(*) FROM movie_languages WHERE kind='unspecified'"))==2
        assert db.scalar(text('SELECT count(*) FROM movie_countries'))==2
        assert db.scalar(text('SELECT character FROM movie_credits WHERE id=5'))=='Hero'
        assert db.scalar(text('SELECT biography FROM persons WHERE id=17'))=='Keep bio'
        assert db.scalar(text('SELECT score FROM ratings WHERE movie_id=99'))==8
        for table in ('users','watchlist','movie_sources','person_sources'):
            assert db.scalar(text(f'SELECT count(*) FROM {table}'))==1
    migrate('downgrade','0005_session_security');migrate('upgrade','head')
    with engine.connect() as db: assert db.scalar(text('SELECT count(*) FROM movie_languages'))==2
    engine.dispose()
