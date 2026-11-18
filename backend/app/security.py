"""Opaque, database-backed sessions. Browser cookies and explicit bearer clients."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import HTTPException, Depends, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from .db import get_db
from .models import User, AuthSession, AuthAttempt, SecurityEvent
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ph = PasswordHasher()
bearer = HTTPBearer(auto_error=False)
COOKIE = 'ca_session'
WEB_ORIGINS = tuple(x.strip() for x in os.getenv('CINEATLAS_WEB_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if x.strip())
COOKIE_SECURE = os.getenv('CINEATLAS_COOKIE_SECURE', 'true').lower() != 'false'
if not WEB_ORIGINS or '*' in WEB_ORIGINS:
    raise RuntimeError('Configure explicit trusted web origins')
# Equalize the expensive password verification path for unknown accounts.
_DUMMY_HASH = ph.hash(secrets.token_urlsafe(32))
WINDOW = 900
LOGIN_IP_LIMIT = 50
LOGIN_IDENTIFIER_LIMIT = 10
REGISTER_IP_LIMIT = 10
PASSWORD_LIMIT = 10


def now(): return datetime.now(timezone.utc)
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def aware(value): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
def hash_password(p): return ph.hash(p)
def verify_password(p, hashed):
    try: return ph.verify(hashed, p)
    except (VerificationError, InvalidHashError): return False


def event(db, kind, user_id=None):
    db.add(SecurityEvent(kind=kind, user_id=user_id))


def quota(db, request, action, identifier=''):
    """Atomic fixed-window increments across workers, before costly password hashing.

    Trust the ASGI peer address, not arbitrary forwarded headers. Deployment must
    configure trusted proxies explicitly. Hash keys to avoid storing raw identifiers.
    """
    ip = request.client.host if request.client else 'unknown'
    bucket = int(now().timestamp()) // WINDOW
    if action == 'login':
        keys = [(digest('login-ip:'+ip), LOGIN_IP_LIMIT),
                (digest('login-pair:'+ip+'\0'+identifier.strip().casefold()), LOGIN_IDENTIFIER_LIMIT)]
    elif action == 'register': keys = [(digest('register-ip:'+ip), REGISTER_IP_LIMIT)]
    else: keys = [(digest('password:'+ip+'\0'+identifier), PASSWORD_LIMIT)]
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    blocked = False
    for key, limit in keys:
        statement = insert(AuthAttempt).values(key=key, bucket=bucket, count=1)
        statement = statement.on_conflict_do_update(index_elements=['key','bucket'], set_={'count': AuthAttempt.count+1}).returning(AuthAttempt.count)
        if db.execute(statement).scalar_one() > limit: blocked = True
    db.execute(delete(AuthAttempt).where(AuthAttempt.bucket < bucket-1))
    # Persist quotas even if login fails. No transaction with the user mutation yet.
    db.commit()
    if blocked:
        raise HTTPException(429, 'Too many authentication attempts. Try again later.', headers={'Retry-After':str(WINDOW-int(now().timestamp())%WINDOW)})


def check_origin(request):
    if request.headers.get('origin') not in WEB_ORIGINS:
        raise HTTPException(403, 'Untrusted browser origin')


def transport_for(request):
    choice = request.headers.get('x-auth-transport', 'bearer')
    if choice not in ('cookie','bearer'): raise HTTPException(400, 'Unsupported authentication transport')
    # Browser authentication must be deliberate, including login CSRF protection.
    if choice == 'cookie': check_origin(request)
    return choice


def issue_session(db, user, request, response, transport, remember=False):
    raw = secrets.token_urlsafe(48)
    created = now()
    lifetime = timedelta(days=30 if remember else 1)
    s = AuthSession(id=str(uuid4()), user_id=user.id, token_hash=digest(raw), transport=transport,
                    created_at=created, expires_at=created+lifetime,
                    device=request.headers.get('user-agent','')[:240])
    db.add(s)
    event(db, 'session_created', user.id)
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    if transport == 'cookie':
        response.set_cookie(COOKIE, raw, httponly=True, secure=COOKIE_SECURE, samesite='strict', path='/api',
                            max_age=int(lifetime.total_seconds()) if remember else None)
        return {'session_id':s.id}
    return {'token':raw, 'session_id':s.id}


def authenticate(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    marker = request.headers.get('x-session-id')
    if credentials is not None:
        raw = credentials.credentials
        transport = 'bearer'
    elif marker:
        raw = request.cookies.get(COOKIE, '')
        transport = 'cookie'
        # Same-origin GET may lack Origin; every cookie mutation requires it.
        if request.method not in ('GET','HEAD','OPTIONS'): check_origin(request)
    else: raise HTTPException(401, 'Please sign in')
    if not raw or len(raw)>256 or (marker and len(marker)>36): raise HTTPException(401, 'Session expired; sign in again')
    s = db.scalar(select(AuthSession).where(AuthSession.token_hash==digest(raw), AuthSession.transport==transport))
    if not s or s.revoked_at is not None or aware(s.expires_at)<=now() or (transport=='cookie' and s.id!=marker):
        raise HTTPException(401, 'Session expired; sign in again')
    u = db.get(User, s.user_id)
    if not u or not u.is_active: raise HTTPException(401, 'Account unavailable')
    return s, u


def current_user(auth=Depends(authenticate)):
    return auth[1]


def require_role(*roles):
    def dependency(user: User = Depends(current_user)):
        if user.role not in roles: raise HTTPException(403, 'Insufficient permissions')
        return user
    return dependency


def active_sessions(db, user_id):
    return db.scalars(select(AuthSession).where(AuthSession.user_id==user_id, AuthSession.revoked_at.is_(None), AuthSession.expires_at>now()).order_by(AuthSession.created_at.desc())).all()


def revoke_all(db, user_id, except_id=None):
    stmt = update(AuthSession).where(AuthSession.user_id==user_id, AuthSession.revoked_at.is_(None))
    if except_id: stmt = stmt.where(AuthSession.id!=except_id)
    db.execute(stmt.values(revoked_at=now()))
