import fakeredis
import pytest

from app import db


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
