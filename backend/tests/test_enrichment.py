import io
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, func, create_engine, inspect, text

from app.db import SessionLocal
from app.enrichment import TMDBClient, ProviderError, read_mapping, enrich
from app.models import Movie, MovieSource, Person, PersonSource, MovieCredit, MovieEnrichmentField

MAPPING = {'Q1':'tt0000001', 'Q2':'tt0000002'}

def seed(two=False):
    with SessionLocal() as db:
        for i in range(1, 3 if two else 2):
            m=Movie(title=f'Fixture {i}',year=2000)
            db.add(m); db.flush()
            db.add(MovieSource(source='wikidata',external_id=f'Q{i}',movie_id=m.id))
        db.commit()


def provider(*, fail=False, ambiguous=False, mismatch=False):
    def respond(r):
        assert r.headers['authorization']=='Bearer fake-token'
        path=r.url.path
        if path.endswith('/configuration'):
            return httpx.Response(200,json={'images':{'secure_base_url':'https://image.tmdb.org/t/p/','poster_sizes':['w500']}})
        if '/find/' in path:
            assert r.url.params['external_source']=='imdb_id'
            i=int(path[-1]); results=[{'id':i}]
            if ambiguous: results.append({'id':999})
            return httpx.Response(200,json={'movie_results':results})
        i=int(path.rsplit('/',1)[1])
        if fail and i==2: return httpx.Response(401,json={'status_message':'secret body'})
        assert r.url.params['append_to_response']=='credits'
        return httpx.Response(200,json={'id':i,'imdb_id':'tt9999999' if mismatch else f'tt{i:07d}', 'release_date':'2000-01-01', 'overview':'Fixture synopsis', 'poster_path':'/test.jpg', 'runtime':100,'credits':{'cast':[{'id':44,'name':'Shared Actor','character':'Hero'},{'id':44,'name':'Shared Actor','character':'Hero'}], 'crew':[{'id':55,'name':'Shared Director','job':'Director'},{'id':55,'name':'Shared Director','job':'Screenplay'},{'id':55,'name':'Shared Director','job':'Sound'}]}})
    return TMDBClient('fake-token',transport=httpx.MockTransport(respond))


def count(db,model): return db.scalar(select(func.count()).select_from(model))


def test_mapping_validation():
    assert read_mapping(io.StringIO('film,imdb\nQ1,tt0000001\n'))=={'Q1':'tt0000001'}
    for data in ['film\nQ1\n','film,imdb\nQ1,bad\n','film,imdb\nQ1,tt0000001\nQ2,tt0000001\n','film,imdb\nQ1,tt0000001\nQ1,tt0000002\n']:
        with pytest.raises(ValueError): read_mapping(io.StringIO(data))


def test_enrich_preview_apply_idempotency_shared_people(client):
    seed(two=True)
    with SessionLocal() as db, provider() as p:
        report=enrich(db,MAPPING,p); assert report.matched==2 and report.people_created==2 and report.credits_created==6
        db.rollback()
        assert count(db,Person)==0 and count(db,MovieSource)==2 and db.get(Movie,1).synopsis==''
        report=enrich(db,MAPPING,p,dry_run=False); db.commit()
        assert report.fields_filled==6 and report.links_created==4
        assert count(db,PersonSource)==2 and count(db,MovieEnrichmentField)==12
        report=enrich(db,MAPPING,p,dry_run=False); db.commit()
        assert not any([report.fields_filled,report.links_created,report.credits_created,report.people_created])
        assert count(db,MovieCredit)==6
    result=client.get('/api/movies/1').json()
    assert result['synopsis']=='Fixture synopsis' and result['poster_url']=='https://image.tmdb.org/t/p/w500/test.jpg'
    assert len(client.get('/api/movies/1/credits').json())==3


def test_manual_fields_and_roles_are_preserved():
    seed()
    with SessionLocal() as db, provider() as p:
        movie=db.get(Movie,1); movie.synopsis='Manual'; movie.poster_url='https://example.org/cover.png'; movie.runtime=123
        person=Person(name='Local Actor');db.add(person);db.flush();db.add(MovieCredit(movie_id=1,person_id=person.id,role='actor',character='Local'));db.commit()
        report=enrich(db,MAPPING,p,dry_run=False);db.commit()
        assert report.fields_filled==0 and movie.synopsis=='Manual' and movie.runtime==123 and movie.poster_url.endswith('cover.png')
        assert [c.character for c in db.scalars(select(MovieCredit).where(MovieCredit.role=='actor'))]==['Local']


@pytest.mark.parametrize('case',['ambiguous','mismatch'])
def test_identity_rejection(case):
    seed()
    with SessionLocal() as db, provider(**{case:True}) as p:
        r=enrich(db,MAPPING,p,dry_run=False); db.commit()
        assert r.skipped==1 and r.matched==0 and count(db,MovieSource)==1 and count(db,Person)==0


def test_provider_error_rolls_back_all_changes():
    seed(two=True)
    with SessionLocal() as db, provider(fail=True) as p:
        with pytest.raises(ProviderError,match='HTTP 401'):
            enrich(db,MAPPING,p,dry_run=False)
        db.rollback()
        assert count(db,Person)==0 and count(db,MovieSource)==2 and db.get(Movie,1).synopsis==''


def test_external_source_conflict():
    seed(two=True)
    with SessionLocal() as db, provider() as p:
        db.add(MovieSource(source='tmdb',external_id='1',movie_id=2));db.commit()
        r=enrich(db,MAPPING,p,dry_run=False,limit=1);db.commit()
        assert r.skipped==1 and count(db,Person)==0 and count(db,MovieSource)==3


def test_migration_from_prior_revision(tmp_path):
    backend=Path(__file__).resolve().parents[1]
    url=f'sqlite:///{tmp_path / "upgrade.db"}'
    env=dict(os.environ,DATABASE_URL=url)
    engine=create_engine(url)
    def upgrade(rev): subprocess.run([sys.executable,'-m','alembic','upgrade',rev],cwd=backend,env=env,check=True,capture_output=True)
    upgrade('0003_catalog_relations')
    with engine.begin() as db:
        db.execute(text("INSERT INTO persons (id,name,biography) VALUES (7,'Old Person','Manual bio')"))
    upgrade('head')
    assert {'movie_enrichment_fields','person_sources'}.issubset(inspect(engine).get_table_names())
    with engine.connect() as db: assert db.scalar(text('SELECT biography FROM persons WHERE id=7'))=='Manual bio'
    subprocess.run([sys.executable,'-m','alembic','check'],cwd=backend,env=env,check=True,capture_output=True)
    engine.dispose()
