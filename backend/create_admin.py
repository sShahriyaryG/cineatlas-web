"""Promote an already-registered account to admin using local operator access.

Usage: python create_admin.py USERNAME
"""
import sys
from sqlalchemy import select
from app.db import SessionLocal
from app.models import User
if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python create_admin.py USERNAME')
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.username==sys.argv[1]))
        if not user:raise SystemExit('User not found; register in the web app first')
        user.role='admin';db.commit();print('Promoted user to admin:',user.username)
