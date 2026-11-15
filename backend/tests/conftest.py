import os,tempfile
_fd,_path=tempfile.mkstemp(suffix='.db');os.close(_fd)
os.environ['DATABASE_URL']='sqlite:///'+_path
import pytest
from fastapi.testclient import TestClient
from app.db import Base,engine
from app.main import app

@pytest.fixture(autouse=True)
def reset():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def client():
    with TestClient(app) as c:yield c
