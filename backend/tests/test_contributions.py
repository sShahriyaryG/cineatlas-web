from app.db import SessionLocal
from app.models import User, Movie, Person, MovieMetadataOverride, PersonMetadataOverride, Contribution
from test_api import headers, seed


def accounts(client):
    editor=headers(client,'editor','ed@example.org'); admin=headers(client,'admin','ad@example.org'); other=headers(client,'other','ot@example.org')
    with SessionLocal() as db:
        for username,role in [('editor','editor'),('admin','admin'),('other','editor')]:
            db.query(User).filter_by(username=username).one().role=role
        db.commit()
    return editor,admin,other


def draft(client,h,entity='movie',target=1,core=None,metadata=None,credits=None):
    baseline=client.get(f'/api/editor/catalog/{entity}/{target}',headers=h).json() if target else None
    changes={'core':core or {},'metadata':metadata or {}}
    if credits is not None:changes['credits']=credits
    r=client.post('/api/me/contributions',headers=h,json=dict(entity=entity,target_id=target,baseline=baseline,changes=changes,reason='Verified source correction'))
    assert r.status_code==201,r.text
    return r.json()


def submit(client,h,d,status=200):
    r=client.post(f'/api/me/contributions/{d["id"]}/submit',headers=h,json={'version':d['version']})
    assert r.status_code==status,r.text
    return r.json()


def review(client,h,d,status=200,decision='approved',note=''):
    r=client.post(f'/api/admin/contributions/{d["id"]}/review',headers=h,json={'version':d['version'],'decision':decision,'note':note})
    assert r.status_code==status,r.text
    return r.json()


def test_editor_draft_private_until_approved_and_metadata_protected(client):
    seed(); e,a,o=accounts(client)
    d=draft(client,e,core={'synopsis':'Corrected film synopsis'},metadata={'original_language':'English','tags':['Fixture'],'certifications':[{'country':'Canada','rating':'PG'}],'soundtracks':[{'title':'Fixture song'}],'quotes':[{'quote':'Synthetic quote','spoiler':True}]})
    assert client.get('/api/me/contributions',headers=o).json()['total']==0
    assert client.get('/api/admin/contributions',headers=a).json()['total']==0
    assert client.patch(f'/api/me/contributions/{d["id"]}',headers=o,json={'version':1,'changes':{}}).status_code==404
    assert client.get('/api/me/contributions').status_code==401
    assert client.get('/api/admin/contributions',headers=e).status_code==403
    pending=submit(client,e,d)
    assert client.get('/api/movies/1').json()['synopsis']=='A journey through space'
    assert client.get('/api/movies/1/metadata').json()['tags']==[]
    assert client.patch(f'/api/me/contributions/{d["id"]}',headers=e,json={'version':pending['version'],'changes':{}}).status_code==409
    review(client,e,pending,403); approved=review(client,a,pending)
    assert approved['result_id']==1 and approved['status']=='approved'
    assert client.get('/api/movies/1').json()['synopsis']=='Corrected film synopsis'
    meta=client.get('/api/movies/1/metadata').json();assert meta['tags']==['Fixture'] and meta['quotes'][0]['spoiler'] and meta['soundtracks'][0]['title']=='Fixture song'
    with SessionLocal() as db:assert db.get(MovieMetadataOverride,(1,'synopsis')) and db.get(MovieMetadataOverride,(1,'original_language'))
    review(client,a,pending,409)


def test_create_person_and_film_shared_credits(client):
    seed();e,a,_=accounts(client)
    d=draft(client,e,'person',None,{'name':'Fixture Person','biography':'Fixture bio'},{'birthday':'1980-01-01','nationalities':['Canada']},[{'related_id':1,'role':'composer'}])
    p=submit(client,e,d);assert client.get('/api/persons',params={'q':'Fixture Person'}).json()['total']==0
    pid=review(client,a,p)['result_id'];assert client.get(f'/api/persons/{pid}').json()['credits'][0]['movie_id']==1
    assert client.get('/api/movies/1/credits').json()[0]['person_id']==pid
    d=draft(client,e,'movie',None,{'title':'Fixture Movie','year':2025,'genres':['Drama']},{'production_countries':['Canada']},[{'related_id':pid,'role':'actor','character':'Hero'}])
    p=submit(client,e,d);assert client.get('/api/movies',params={'q':'Fixture Movie'}).json()['total']==0
    mid=review(client,a,p)['result_id'];assert client.get(f'/api/movies/{mid}/credits').json()[0]['character']=='Hero'
    assert len(client.get(f'/api/persons/{pid}').json()['credits'])==2
    d=draft(client,e,'person',pid,{}, {'birthplace':'Fixture town'}, [])
    review(client,a,submit(client,e,d));assert client.get(f'/api/movies/{mid}/credits').json()==[]
    with SessionLocal() as db:assert db.get(MovieMetadataOverride,(mid,'credits_actor')) and db.get(PersonMetadataOverride,(pid,'birthplace'))


def test_conflicting_proposals_and_direct_update(client):
    seed();e,a,o=accounts(client)
    d1=submit(client,e,draft(client,e,core={'runtime':110}));d2=submit(client,o,draft(client,o,core={'runtime':120}))
    review(client,a,d1);review(client,a,d2,409)
    assert client.get('/api/movies/1').json()['runtime']==110
    assert client.get('/api/admin/contributions',headers=a,params={'status':'pending'}).json()['total']==1
    d=submit(client,e,draft(client,e,metadata={'tags':['Fixture']}))
    assert client.patch('/api/movies/1/metadata',headers=a,json={'tags':['Direct edit']}).status_code==200
    review(client,a,d,409)


def test_draft_lifecycle_ownership_and_versions(client):
    seed();e,a,o=accounts(client)
    d=draft(client,e,core={'runtime':110});path=f'/api/me/contributions/{d["id"]}'
    patch={'version':d['version'],'changes':{'core':{'runtime':120}},'reason':'Updated correction'}
    r=client.patch(path,headers=e,json=patch);assert r.status_code==200,r.text
    assert client.patch(path,headers=e,json=patch).status_code==409
    pending=submit(client,e,r.json());assert client.post(path+'/withdraw',headers=o,json={'version':pending['version']}).status_code==404
    w=client.post(path+'/withdraw',headers=e,json={'version':pending['version']});assert w.json()['status']=='withdrawn'
    review(client,a,pending,409)
    rejected=submit(client,e,draft(client,e,core={'runtime':100}));review(client,a,rejected,422,'rejected');r=review(client,a,rejected,200,'rejected','Source is insufficient');assert r['review_note']=='Source is insufficient'
    d=draft(client,e,core={'runtime':130});assert client.delete(f'/api/me/contributions/{d["id"]}?version={d["version"]}',headers=e).status_code==204
    assert client.get('/api/movies/1').json()['runtime'] is None


def test_validation_and_duplicate_handling(client):
    seed();e,a,_=accounts(client)
    for d,code in [(draft(client,e,'movie',None,{'title':'Orbit','year':2020}),409),(draft(client,e,'movie',None,{'title':'Incomplete'}),422),(draft(client,e,core={'runtime':130},credits=[{'related_id':999,'role':'actor'}]),422),(draft(client,e,core={}),422)]:submit(client,e,d,code)
    assert client.get('/api/movies/1').json()['runtime'] is None
    r=client.post('/api/me/contributions',headers=e,json={'entity':'movie','changes':{'core':{'runtime':-1}}});assert r.status_code==422
    d=draft(client,e,'person',None,{'name':'New person'},{'birthday':'2000-01-01','deathday':'1990-01-01'});submit(client,e,d,422)
    d1=submit(client,e,draft(client,e,'movie',None,{'title':'New duplicate','year':2024}));d2=submit(client,e,draft(client,e,'movie',None,{'title':'New duplicate','year':2024}));review(client,a,d1);review(client,a,d2,409)


def test_missing_records_legacy_withdraw_and_self_review(client):
    seed();e,a,o=accounts(client)
    missing=client.get('/api/editor/missing/movie',headers=e,params={'field':'runtime'}).json();assert missing['total']==2
    assert client.get('/api/editor/missing/person',headers=e,params={'field':'deathday'}).status_code==422
    d=submit(client,a,draft(client,a,core={'runtime':120}));review(client,a,d,403)
    r=client.post('/api/movies/1/suggestions',headers=e,json={'synopsis':'Legacy proposal','reason':'Correction'});sid=r.json()['id']
    assert client.post(f'/api/me/suggestions/{sid}/withdraw',headers=o).status_code==404
    assert client.post(f'/api/me/suggestions/{sid}/withdraw',headers=e).json()['status']=='withdrawn'
    assert client.post(f'/api/admin/suggestions/{sid}/approved',headers=a).status_code==409


def test_credit_order_preserved_on_person_edit_and_conflict(client):
    seed(); e,a,_=accounts(client)
    with SessionLocal() as db:
        db.add_all([Person(name='Alpha'),Person(name='Zulu')]);db.commit()
    d=draft(client,e,credits=[{'related_id':1,'role':'actor','position':1},{'related_id':2,'role':'actor','position':0}])
    review(client,a,submit(client,e,d))
    credits=client.get('/api/movies/1/credits').json();assert [x['person_id'] for x in credits]==[2,1]
    d=draft(client,e,'person',1,{'biography':'Updated biography'},credits=[{'related_id':1,'role':'actor'},{'related_id':2,'role':'director'}])
    review(client,a,submit(client,e,d))
    credits=client.get('/api/movies/1/credits').json();assert [(x['person_id'],x['position']) for x in credits]==[(2,0),(1,1)]
    assert client.get('/api/movies/2/credits').json()[0]['role']=='director'


def test_stale_baseline_for_draft_and_history_survives_movie_delete(client):
    seed(); e,a,_=accounts(client)
    baseline=client.get('/api/editor/catalog/movie/1',headers=e).json()
    client.patch('/api/movies/1/metadata',headers=a,json={'tags':['New tag']})
    r=client.post('/api/me/contributions',headers=e,json={'entity':'movie','target_id':1,'baseline':baseline,'changes':{'core':{'runtime':120}}});assert r.status_code==409
    d=submit(client,e,draft(client,e,core={'runtime':120}));review(client,a,d)
    assert client.delete('/api/movies/1',headers=a).status_code==204
    row=client.get('/api/me/contributions',headers=e).json()['items'][0];assert row['status']=='approved' and row['target_id']==1 and row['baseline']['core']['title']=='Orbit'


def test_readable_contribution_validation_errors(client):
    seed(); e,a,_=accounts(client)
    invalid={'entity':'movie','changes':{'core':{'year':1700,'runtime':-3}}}
    r=client.post('/api/me/contributions',headers=e,json=invalid)
    assert r.status_code==422
    assert r.json()['detail']=='Enter a whole release year between 1888 and 2200.\nEnter a whole runtime between 1 and 10,000 minutes.'
    d=draft(client,e,core={'runtime':90})
    r=client.patch(f'/api/me/contributions/{d["id"]}',headers=e,json={'version':d['version'],'changes':{'core':{'runtime':10001}}})
    assert r.status_code==422 and r.json()['detail']=='Enter a whole runtime between 1 and 10,000 minutes.'
    assert client.get('/api/me/contributions',headers=e).json()['items'][0]['changes']['core']['runtime']==90
    r=client.post('/api/me/contributions',headers=e,json={'entity':'movie','source_url':'not a URL','changes':{}})
    assert r.status_code==422 and r.json()['detail']=='Supporting source URL: Enter a valid HTTP or HTTPS URL without credentials.'
    r=client.post('/api/me/contributions',headers=e,json={'entity':'person','changes':{'metadata':{'birthday':'not-a-date'}}})
    assert r.status_code==422 and r.json()['detail']=='Birthday: Enter a valid calendar date.'
    assert client.get('/api/admin/contributions',headers=a).json()['total']==0


def test_all_submitted_history_is_durable_for_both_roles(client):
    seed();e,a,o=accounts(client)
    pending=submit(client,e,draft(client,e,core={'runtime':90}))
    rejected=review(client,a,submit(client,e,draft(client,e,core={'runtime':91})),decision='rejected',note='Evidence insufficient')
    w=submit(client,e,draft(client,e,core={'runtime':92}))
    withdrawn=client.post(f'/api/me/contributions/{w["id"]}/withdraw',headers=e,json={'version':w['version']}).json()
    private=draft(client,e,core={'runtime':93})
    approved=review(client,a,pending)
    assert client.get('/api/admin/contributions',headers=a,params={'status':'pending'}).json()['total']==0
    rows=client.get('/api/admin/contributions',headers=a).json()
    assert rows['total']==3 and {c['id']:c['status'] for c in rows['items']}=={approved['id']:'approved',rejected['id']:'rejected',withdrawn['id']:'withdrawn'}
    assert client.get('/api/admin/contributions',headers=a,params={'status':'draft'}).json()['total']==0
    for status in ('approved','rejected','withdrawn'):
        assert client.get('/api/admin/contributions',headers=a,params={'status':status}).json()['total']==1
    mine=client.get('/api/me/contributions',headers=e).json()
    assert mine['total']==4 and private['id'] in {c['id'] for c in mine['items']}
    assert client.get('/api/me/contributions',headers=o).json()['total']==0
    assert client.get('/api/admin/contributions',headers=a,params={'size':1,'page':2}).json()['total']==3
    with SessionLocal() as db:
        assert db.get(Contribution,approved['id']).status=='approved'
        assert db.get(Contribution,rejected['id']).review_note=='Evidence insufficient'


def test_unified_history_paginates_both_kinds_and_preserves_actions(client):
    seed();e,a,o=accounts(client)
    private=draft(client,e,core={'runtime':110})
    legacy=client.post('/api/movies/1/suggestions',headers=e,json={'synopsis':'Earlier synopsis correction','reason':'Verified correction'}).json()
    pending=submit(client,e,draft(client,e,'person',None,{'name':'New fixture person'}))
    other=draft(client,o,core={'runtime':130})
    mine='/api/me/contribution-history'; admin_path='/api/admin/contribution-history'
    first=client.get(mine,headers=e,params={'size':2}).json()
    second=client.get(mine,headers=e,params={'size':2,'page':2}).json()
    assert first['total']==second['total']==3
    rows=first['items']+second['items']
    assert [(r['kind'],r['id']) for r in rows]==[('structured',pending['id']),('synopsis',legacy['id']),('structured',private['id'])]
    # Numeric IDs from different tables can be the same; kind disambiguates.
    assert private['id']==legacy['id']
    assert client.get(mine,headers=o).json()['items'][0]['id']==other['id']
    assert client.get(mine).status_code==401
    assert client.get(admin_path,headers=e).status_code==403
    assert client.get(admin_path,headers=a,params={'status':'draft'}).json()['total']==0
    queued=client.get(admin_path,headers=a,params={'status':'pending'}).json()
    assert queued['total']==2 and {r['kind'] for r in queued['items']}=={'structured','synopsis'}
    synopsis=next(r for r in queued['items'] if r['kind']=='synopsis')
    assert synopsis['current_synopsis']=='A journey through space' and synopsis['author_name']=='editor'
    assert client.post(f'/api/admin/suggestions/{legacy["id"]}/approved',headers=a).status_code==200
    review(client,a,pending)
    approved=client.get(admin_path,headers=a,params={'status':'approved'}).json()
    assert approved['total']==2
    assert 'current_synopsis' not in next(r for r in approved['items'] if r['kind']=='synopsis')
    assert client.get(admin_path,headers=a,params={'status':'pending'}).json()['total']==0
    assert client.get(mine,headers=e,params={'status':'draft'}).json()['total']==1
    assert client.get('/api/me/suggestions',headers=e).json()[0]['status']=='approved'
