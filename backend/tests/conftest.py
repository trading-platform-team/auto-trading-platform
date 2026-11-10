import fakeredis
import pytest

from app import db
from app.auth import security


@pytest.fixture(autouse=True)
def jwt_secret():
    security.set_secret("test-secret")
    yield


def login(client, username="tester", password="password123"):
    """회원가입 후 토큰을 기본 헤더로 설정"""
    res = client.post("/auth/register", json={"username": username, "password": password})
    if res.status_code == 409:
        res = client.post("/auth/login", json={"username": username, "password": password})
    client.headers["Authorization"] = f"Bearer {res.json()['access_token']}"
    return res.json()


@pytest.fixture
def sqlite_db():
    """테스트마다 새 SQLite 메모리 DB"""
    db.configure("sqlite+pysqlite:///:memory:")
    db.init_db(retries=1)
    yield
    db.Base.metadata.drop_all(db.engine)
    db.engine = None


@pytest.fixture
def fake_redis():
    return fakeredis.FakeAsyncRedis(decode_responses=True)
