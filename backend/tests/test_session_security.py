from datetime import timedelta
import hashlib
from sqlalchemy import select
from fastapi.testclient import TestClient
from app.db import SessionLocal
from app.models import AuthSession, SecurityEvent, User
from app.main import app
from app import security

PASSWORD = 'test-password-123'
ORIGIN = 'http://localhost:5173'
BROWSER = {'Origin': ORIGIN, 'X-Auth-Transport': 'cookie'}


def signup(client, name='sessionuser', **options):
    r = client.post('/api/auth/register', json={'username':name,'email':name+'@example.org','password':PASSWORD,**options})
    assert r.status_code == 201, r.text
    return r.json()


def login(client, name='sessionuser', password=PASSWORD, **options):
    return client.post('/api/auth/login', json={'identifier':name,'password':password,**options})


def auth(result): return {'Authorization':'Bearer '+result['token']}


def test_durable_hash_only_and_restart(client):
    data = signup(client)
    with SessionLocal() as db:
        s = db.get(AuthSession,data['session_id'])
        assert s.token_hash == hashlib.sha256(data['token'].encode()).hexdigest()
        assert data['token'] not in str(s.__dict__)
        assert security.aware(s.expires_at)-security.aware(s.created_at) == timedelta(days=1)
    # New TestClient and a new database session; no process-local token map exists.
    with TestClient(app) as other:
        assert other.get('/api/auth/me',headers=auth(data)).json()['username']=='sessionuser'


def test_cookie_transport_and_csrf(client,monkeypatch):
    monkeypatch.setattr(security,"COOKIE_SECURE",True)
    signup(client)
    with TestClient(app,base_url='https://localhost:8000') as browser:
        r=browser.post('/api/auth/login',headers=BROWSER,json={'identifier':'sessionuser','password':PASSWORD,'remember':True})
        assert r.status_code==200, r.text
        assert 'token' not in r.json()
        cookie=r.headers['set-cookie'].lower()
        for attr in ('httponly','secure','samesite=strict','max-age=2592000','path=/api'):
            assert attr in cookie
        ident=r.json()['session_id']; header={'X-Session-ID':ident,'Origin':ORIGIN}
        assert browser.get('/api/auth/me',headers=header).status_code==200
        assert browser.get('/api/auth/me').status_code==401
        assert browser.get('/api/auth/me',headers={'X-Session-ID':'wrong'}).status_code==401
        raw=browser.cookies.get(security.COOKIE)
        assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+raw}).status_code==401
        assert browser.patch('/api/auth/me',headers={'X-Session-ID':ident},json={'bio':'bad'}).status_code==403
        assert browser.patch('/api/auth/me',headers={**header,'Origin':'https://attacker.example'},json={'bio':'bad'}).status_code==403
        assert browser.patch('/api/auth/me',headers=header,json={'bio':'good'}).status_code==200
        assert browser.post('/api/auth/logout',headers=header).status_code==204
        assert browser.get('/api/auth/me',headers=header).status_code==401


def test_cross_tab_cookie_binding(client):
    signup(client,'alice'); signup(client,'bob')
    with TestClient(app,base_url='https://localhost:8000') as browser:
        a=browser.post('/api/auth/login',headers=BROWSER,json={'identifier':'alice','password':PASSWORD}).json()
        b=browser.post('/api/auth/login',headers=BROWSER,json={'identifier':'bob','password':PASSWORD}).json()
        old={'X-Session-ID':a['session_id'],'Origin':ORIGIN}
        new={'X-Session-ID':b['session_id'],'Origin':ORIGIN}
        assert browser.get('/api/auth/me',headers=old).status_code==401
        assert browser.post('/api/auth/logout',headers=old).status_code==401
        assert browser.get('/api/auth/me',headers=new).json()['username']=='bob'


def test_untrusted_cookie_login_and_cors(client):
    signup(client)
    r=client.post('/api/auth/login',headers={'X-Auth-Transport':'cookie','Origin':'https://attacker.example'},json={'identifier':'sessionuser','password':PASSWORD})
    assert r.status_code==403 and 'set-cookie' not in r.headers
    headers={'Origin':ORIGIN,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'x-session-id,x-auth-transport,content-type'}
    assert client.options('/api/auth/login',headers=headers).status_code==200
    assert client.options('/api/auth/login',headers={**headers,'Origin':'https://attacker.example'}).status_code==400


def test_session_list_revoke_and_account_isolation(client):
    a=signup(client,'alice'); other=signup(client,'bob'); b=login(client,'alice').json()
    h=auth(a)
    r=client.get('/api/auth/sessions',headers=h)
    assert r.headers['cache-control']=='no-store'
    assert {s['id'] for s in r.json()}=={a['session_id'],b['session_id']}
    assert [s['id'] for s in r.json() if s['current']]==[a['session_id']]
    assert all('token' not in s and 'token_hash' not in s for s in r.json())
    assert client.delete('/api/auth/sessions/'+other['session_id'],headers=h).status_code==404
    assert client.delete('/api/auth/sessions/'+b['session_id'],headers=h).status_code==204
    assert client.get('/api/auth/me',headers=auth(b)).status_code==401
    assert client.get('/api/auth/me',headers=h).status_code==200
    assert client.post('/api/auth/logout-all',headers=h).status_code==204
    assert client.get('/api/auth/me',headers=h).status_code==401
    assert client.get('/api/auth/me',headers=auth(other)).status_code==200


def test_expired_and_inactive_accounts(client):
    a=signup(client); b=login(client).json()
    with SessionLocal() as db:
        db.get(AuthSession,a['session_id']).expires_at=security.now()-timedelta(seconds=1)
        db.commit()
    assert client.get('/api/auth/me',headers=auth(a)).status_code==401
    with SessionLocal() as db:
        db.get(User,a['user']['id']).is_active=False;db.commit()
    assert client.get('/api/auth/me',headers=auth(b)).status_code==401
    assert login(client).status_code==401


def test_password_change_revokes_other_sessions(client):
    a=signup(client); b=login(client).json(); h=auth(a)
    path='/api/auth/password'; new='new-long-password-123'
    assert client.post(path,headers=h,json={'current_password':'wrong','new_password':new}).status_code==400
    assert client.get('/api/auth/me',headers=h).status_code==200
    assert client.post(path,headers=h,json={'current_password':PASSWORD,'new_password':new}).status_code==204
    assert client.get('/api/auth/me',headers=auth(b)).status_code==401
    assert client.get('/api/auth/me',headers=h).status_code==200
    assert login(client).status_code==401
    assert login(client,password=new).status_code==200
    with SessionLocal() as db:
        kinds=set(db.scalars(select(SecurityEvent.kind)))
        assert {'session_created','login_failed','password_change_failed','password_changed'} <= kinds


def test_login_quota_is_persistent_and_window_expires(client,monkeypatch):
    signup(client);monkeypatch.setattr(security,'LOGIN_IDENTIFIER_LIMIT',2)
    fixed=security.now();monkeypatch.setattr(security,'now',lambda:fixed)
    for _ in range(2):assert login(client,password='wrong').status_code==401
    with TestClient(app) as other:
        blocked=login(other);assert blocked.status_code==429 and int(blocked.headers['retry-after'])>0
    monkeypatch.setattr(security,'now',lambda:fixed+timedelta(seconds=security.WINDOW))
    assert login(client).status_code==200


def test_registration_quota(client,monkeypatch):
    monkeypatch.setattr(security,'REGISTER_IP_LIMIT',1)
    signup(client,'first')
    r=client.post('/api/auth/register',json={'username':'second','email':'second@example.org','password':PASSWORD})
    assert r.status_code==429
