"""Fictional provider fixtures, no live calls or credentials."""
import httpx
import pytest
from sqlalchemy import select, func

from app.db import SessionLocal
from app.enrichment import ProviderError
from app.enrichment_v2 import EnrichmentClient, enrich_linked
from app.models import (Movie, MovieSource, MovieCredit, MovieEnrichmentField, MovieMetadataOverride,
    Person, PersonSource, PersonEnrichmentField, PersonMetadataOverride, Language, Country, MovieMetadata)
from app.metadata import (apply_movie_metadata, MovieMetadataPatch, movie_metadata_out, person_metadata_out,
    apply_person_metadata, PersonMetadataPatch, sync_legacy_labels)


def seed(db, *, two=False, legacy=''):
    for i in range(1,3 if two else 2):
        movie=Movie(title=f'Fixture {i}',year=2000,language=legacy)
        db.add(movie);db.flush()
        sync_legacy_labels(db,movie)
        db.add_all([MovieSource(source='tmdb',external_id=str(i),movie_id=movie.id),
                    MovieSource(source='imdb',external_id=f'tt{i:07d}',movie_id=movie.id)])
    db.commit()


def provider(*, bad_movie=False, bad_person=False, fail=False, missing_person=False, invalid_date=False, counters=None):
    def respond(r):
        assert r.headers['authorization']=='Bearer fixture-only'
        path=r.url.path
        if path.endswith('/configuration'):
            return httpx.Response(200,json={'images':{'secure_base_url':'https://image.tmdb.org/t/p/','poster_sizes':['w500'],'profile_sizes':['w185']}})
        if path.endswith('/languages'):
            return httpx.Response(200,json=[{'iso_639_1':'en','english_name':'English'},{'iso_639_1':'fr','english_name':'French'}])
        if path.endswith('/countries'):
            return httpx.Response(200,json=[{'iso_3166_1':'US','english_name':'United States'},{'iso_3166_1':'FR','english_name':'France'}])
        i=int(path.rsplit('/',1)[1])
        if '/person/' in path:
            if counters is not None: counters.append(i)
            if fail: return httpx.Response(401,json={'message':'must not leak'})
            if missing_person: return httpx.Response(404,json={})
            return httpx.Response(200,json={'id':i+1 if bad_person else i,'biography':'Fixture bio','profile_path':'/face.jpg',
                'birthday':'1980-01-01','deathday':'1970-01-01' if invalid_date else '2020-01-01',
                'place_of_birth':'Fixture City','also_known_as':['Other Name','other name'],'name':'Not verified full name'})
        assert 'release_dates' in r.url.params['append_to_response']
        return httpx.Response(200,json={'id':i,'imdb_id':'tt9999999' if bad_movie else f'tt{i:07d}',
            'release_date':'2000-01-02','status':'Released','original_title':'Original fixture',
            'original_language':'en','spoken_languages':[{'iso_639_1':'en'},{'iso_639_1':'fr'}],
            'production_countries':[{'iso_3166_1':'US'},{'iso_3166_1':'FR'}], 'overview':'Fixture synopsis',
            'poster_path':'/poster.jpg','runtime':100,
            'alternative_titles':{'titles':[{'title':'Another title'},{'title':'another title'}]},
            'keywords':{'keywords':[{'name':'Adventure'}]},
            'release_dates':{'results':[{'iso_3166_1':'US','release_dates':[{'certification':'PG'},{'certification':'PG'},{'certification':''}]}]},
            'videos':{'results':[{'site':'YouTube','type':'Trailer','official':True,'key':'abcDEF12345'}]},
            'credits':{'cast':[{'id':44,'name':'Actor','character':'Hero'}],'crew':[
                {'id':55,'name':'Crew','job':'Original Music Composer'},{'id':55,'name':'Crew','job':'Director of Photography'},
                {'id':55,'name':'Crew','job':'Editor'},{'id':55,'name':'Crew','job':'Unmapped job'}]}})
    return EnrichmentClient('fixture-only',transport=httpx.MockTransport(respond),interval=0)


def count(db, model): return db.scalar(select(func.count()).select_from(model))


def test_preview_apply_repeat_and_shared_people():
    requests=[]
    with SessionLocal() as db, provider(counters=requests) as p:
        seed(db,two=True)
        report=enrich_linked(db,p)
        assert report.matched==2 and report.persons_matched==2 and report.credits_created==8
        assert len(requests)==2 and report.person_fields_filled==12
        db.rollback()
        assert count(db,Person)==0 and count(db,Language)==0 and count(db,MovieMetadata)==0
        assert db.get(Movie,1).synopsis==''
        report=enrich_linked(db,p,dry_run=False);db.commit()
        data=movie_metadata_out(db,db.get(Movie,1))
        assert data['original_language']=='English' and data['spoken_languages']==['English','French']
        assert data['production_countries']==['France','United States'] and data['certifications']==[{'country':'United States','rating':'PG'}]
        assert data['alternative_titles']==['Another title'] and data['tags']==['Adventure']
        assert data['trailer_url'].endswith('abcDEF12345') and data['release_status']=='released'
        assert db.scalar(select(Language.code).where(Language.name=='English'))=='en'
        assert db.scalar(select(Country.code).where(Country.name=='France'))=='FR'
        person=db.scalar(select(Person).order_by(Person.id))
        pdata=person_metadata_out(db,person)
        assert pdata['profile_url']=='https://image.tmdb.org/t/p/w185/face.jpg' and pdata['nationalities']==[] and pdata['full_name'] is None
        assert person.biography=='Fixture bio' and pdata['alternative_names']==['Other Name']
        assert {c.role for c in db.scalars(select(MovieCredit))}=={'actor','composer','cinematographer','editor'}
        assert count(db,PersonEnrichmentField)==12
        again=enrich_linked(db,p,dry_run=False);db.commit()
        assert (again.fields_filled,again.person_fields_filled,again.people_created,again.credits_created,again.classification_codes_added)==(0,0,0,0,0)
        assert count(db,Movie)==2 and count(db,MovieCredit)==8


def test_manual_values_and_explicit_clears_remain():
    with SessionLocal() as db, provider() as p:
        seed(db,legacy='French')
        m=db.get(Movie,1);m.synopsis='Manual synopsis'
        apply_movie_metadata(db,m,MovieMetadataPatch(tags=['Manual'],production_countries=['France']))
        db.add_all([MovieMetadataOverride(movie_id=1,field=f) for f in ('poster_url','unspecified_languages','certifications','credits_composer')])
        person=Person(name='Actor',biography='Manual bio');db.add(person);db.flush()
        pid=person.id
        db.add(PersonSource(source='tmdb',external_id='44',person_id=pid))
        db.add(PersonMetadataOverride(person_id=pid,field='profile_url'))
        apply_person_metadata(db,person,PersonMetadataPatch(birthday='1979-01-01'))
        db.commit()
        enrich_linked(db,p,dry_run=False);db.commit()
        data=movie_metadata_out(db,m)
        assert m.synopsis=='Manual synopsis' and m.poster_url==''
        assert data['tags']==['Manual'] and data['production_countries']==['France'] and data['certifications']==[]
        assert data['unspecified_languages']==['French'] and data['original_language'] is None and data['spoken_languages']==[]
        assert not db.scalar(select(MovieCredit.id).where(MovieCredit.role=='composer'))
        pdata=person_metadata_out(db,person)
        assert person.biography=='Manual bio' and pdata['profile_url'] is None and pdata['birthday'].year==1979


def test_legacy_exact_reconciliation_and_conflict():
    with SessionLocal() as db, provider() as p:
        seed(db,legacy='English')
        db.add(Country(name='United States',key='united states',code='GB'));db.commit()
        r=enrich_linked(db,p,dry_run=False);db.commit()
        data=movie_metadata_out(db,db.get(Movie,1))
        assert data['original_language']=='English' and data['unspecified_languages']==[]
        assert data['production_countries']==[] and data['certifications']==[]
        assert count(db,Country)==1 and any('different code' in s for s in r.issues)


def test_bad_movie_identity_skips_without_writes():
    with SessionLocal() as db, provider(bad_movie=True) as p:
        seed(db)
        report=enrich_linked(db,p,dry_run=False);db.commit()
        assert report.skipped==1 and report.matched==0 and count(db,Person)==0 and count(db,MovieEnrichmentField)==0


@pytest.mark.parametrize('case',['bad_person','missing_person'])
def test_bad_person_identity_skips_without_profile_changes(case):
    with SessionLocal() as db, provider(**{case:True}) as p:
        seed(db)
        report=enrich_linked(db,p,dry_run=False);db.commit()
        assert report.matched==1 and report.persons_skipped==2 and count(db,PersonEnrichmentField)==0


def test_provider_failure_rolls_back_selected_batch():
    with SessionLocal() as db, provider(fail=True) as p:
        seed(db)
        with pytest.raises(ProviderError,match='HTTP 401') as exc:
            enrich_linked(db,p,dry_run=False)
        assert 'must not leak' not in str(exc.value)
        db.rollback()
        assert count(db,MovieMetadata)==count(db,Person)==count(db,Language)==0
        assert db.get(Movie,1).synopsis==''


def test_invalid_dates_and_cursor():
    with SessionLocal() as db, provider(invalid_date=True) as p:
        seed(db,two=True)
        db.add(Movie(title='No link',year=2000));db.commit()
        r=enrich_linked(db,p,after_movie_id=1,limit=1,dry_run=False);db.commit()
        assert r.last_movie_id==2 and r.candidates==1 and r.unlinked_movies==1
        assert db.get(Movie,1).synopsis=='' and db.get(Movie,2).synopsis
        assert all(person_metadata_out(db,x)['deathday'] is None for x in db.scalars(select(Person)))
        assert any('invalid deathday' in s for s in r.issues)


def test_history_protects_previously_imported_then_removed_values():
    with SessionLocal() as db, provider() as p:
        seed(db)
        enrich_linked(db,p,dry_run=False);db.commit()
        m=db.get(Movie,1); person=db.scalar(select(Person).order_by(Person.id))
        apply_movie_metadata(db,m,MovieMetadataPatch(tags=[]))
        apply_person_metadata(db,person,PersonMetadataPatch(profile_url=None));person.biography=''
        db.commit()
        r=enrich_linked(db,p,dry_run=False);db.commit()
        assert r.person_fields_filled==r.fields_filled==0 and movie_metadata_out(db,m)['tags']==[]
        assert person_metadata_out(db,person)['profile_url'] is None and person.biography==''


def test_admin_base_edits_and_credit_removal_create_overrides(client):
    from test_catalog import admin
    h=admin(client)
    m=client.post('/api/movies',headers=h,json={'title':'Fixture','year':2000,'genres':'Drama',
        'synopsis':'Old manual value','poster_url':'https://example.org/poster','runtime':90}).json()
    p=client.post('/api/persons',headers=h,json={'name':'Existing person','biography':'Old bio'}).json()
    mid,pid=m['id'],p['id']
    assert client.put(f'/api/movies/{mid}',headers=h,json={'title':'Fixture','year':2000,'genres':'Drama',
        'synopsis':'','poster_url':'','runtime':None}).status_code==200
    assert client.put(f'/api/persons/{pid}',headers=h,json={'name':'Existing person','biography':''}).status_code==200
    credit=client.post(f'/api/movies/{mid}/credits',headers=h,json={'person_id':pid,'role':'composer'})
    assert credit.status_code==201
    assert client.delete(f'/api/movies/{mid}/credits/{credit.json()["id"]}',headers=h).status_code==204
    with SessionLocal() as db:
        assert all(db.get(MovieMetadataOverride,(mid,f)) is not None for f in ('synopsis','poster_url','runtime','credits_composer'))
        assert db.get(PersonMetadataOverride,(pid,'biography')) is not None


def test_classifier_savepoint_dry_run_without_earlier_writes():
    with SessionLocal() as db, provider() as p:
        seed(db)
        m=db.get(Movie,1);m.synopsis='Manual';m.poster_url='https://example.org/image';m.runtime=90
        apply_movie_metadata(db,m,MovieMetadataPatch(original_title='Manual',release_date='2000-01-01',
            release_status='released',trailer_url='https://example.org/video',alternative_titles=['Manual'],tags=['Manual']))
        db.add_all([MovieMetadataOverride(movie_id=1,field='credits_'+role) for role in ('actor','composer','cinematographer','editor')]);db.commit()
        r=enrich_linked(db,p);assert r.classification_codes_added>0
        db.rollback()
        assert count(db,Language)==count(db,Country)==count(db,MovieEnrichmentField)==0
        assert movie_metadata_out(db,m)['original_language'] is None


@pytest.mark.parametrize('legacy,expected',[('French','English'),('Unmapped legacy value',None)])
def test_legacy_spoken_language_is_reconciled_in_one_pass_or_preserved(legacy,expected):
    with SessionLocal() as db, provider() as p:
        seed(db,legacy=legacy)
        enrich_linked(db,p,dry_run=False);db.commit()
        movie=db.get(Movie,1);data=movie_metadata_out(db,movie)
        assert data['original_language']==expected and movie.language==legacy
        assert data['unspecified_languages']==([] if expected else [legacy])
        r=enrich_linked(db,p,dry_run=False);db.commit()
        assert r.fields_filled==r.person_fields_filled==0
