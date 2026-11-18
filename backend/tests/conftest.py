import fakeredis
import pytest

from app import db
from app.auth import security
from app.core.config import settings


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    """테스트에서 실제 외부 API를 호출하거나 운영용 비밀값을 사용하지 않는다."""
    security.set_secret("test-secret")
    monkeypatch.setattr(settings, "external_events_enabled", False)
    monkeypatch.setattr(settings, "kiwoom_app_key", "")  # 키움은 가짜 서버(tests/test_stocks.py)로만 시험
    monkeypatch.setattr(settings, "kiwoom_secret_key", "")
    monkeypatch.setattr(settings, "public_data_service_key", "")  # 공공데이터도 전용 Mock 테스트에서만 호출
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
