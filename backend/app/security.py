import hashlib, hmac, secrets, os
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .db import get_db
from .models import User
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

ph=PasswordHasher()
bearer=HTTPBearer(auto_error=False)
# Tokens are stored by hash in process memory: restart logs out users; no default static signing key.
# Production deployments should use durable, revocable server-side sessions (e.g. Redis).
_sessions: dict[str, tuple[int, datetime]]={}
def hash_password(p): return ph.hash(p)
def verify_password(p, digest):
    try: return ph.verify(digest,p)
    except (VerifyMismatchError,VerificationError): return False

def create_token(user_id):
    token=secrets.token_urlsafe(48)
    _sessions[hashlib.sha256(token.encode()).hexdigest()]=(user_id,datetime.now(timezone.utc)+timedelta(days=7))
    return token

def revoke_token(token): _sessions.pop(hashlib.sha256(token.encode()).hexdigest(),None)
def current_user(credentials: HTTPAuthorizationCredentials | None=Depends(bearer),db: Session=Depends(get_db)):
    if credentials is None: raise HTTPException(401,'Please sign in')
    entry=_sessions.get(hashlib.sha256(credentials.credentials.encode()).hexdigest())
    if not entry or entry[1] < datetime.now(timezone.utc): raise HTTPException(401,'Session expired; sign in again')
    u=db.get(User,entry[0])
    if not u or not u.is_active: raise HTTPException(401,'Account unavailable')
    return u

def require_role(*roles):
    def dependency(user:User=Depends(current_user)):
        if user.role not in roles: raise HTTPException(403,'Insufficient permissions')
        return user
    return dependency
