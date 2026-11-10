import pytest
from fastapi.testclient import TestClient

from app.auth import vault
from app.auth.security import create_token, decode_token, hash_password, set_secret, verify_password
from app.main import app
from tests.conftest import login

RSI = [{"left": {"name": "RSI", "period": 14}, "op": "<", "right": 30}]


def test_password_hash():
    h = hash_password("secret-pass")
    assert "secret-pass" not in h and h != hash_password("secret-pass")  # salt
    assert verify_password("secret-pass", h) and not verify_password("wrong", h)


def test_token_roundtrip_and_tamper():
    t = create_token(3, "alice")
    assert decode_token(t) == {"id": 3, "username": "alice"}
    set_secret("other-key")
    assert decode_token(t) is None  # 다른 키로 서명된 토큰 거부
    assert decode_token("not-a-token") is None


def test_vault_fallback(monkeypatch):
    monkeypatch.setattr(vault.settings, "vault_addr", "http://127.0.0.1:9")
    monkeypatch.setattr(vault.settings, "jwt_secret", "")
    _, source = vault.load_jwt_secret(retries=1)
    assert source == "temporary"
    monkeypatch.setattr(vault.settings, "jwt_secret", "from-env")
    assert vault.load_jwt_secret(retries=1) == ("from-env", "env")


def test_vault_creates_and_reuses_secret(monkeypatch):
    store = {}
    monkeypatch.setattr(vault, "read_secrets", lambda: dict(store))
    monkeypatch.setattr(vault, "write_secrets", lambda d: store.update(d) or True)
    first, src1 = vault.load_jwt_secret()
    second, src2 = vault.load_jwt_secret()
    assert (src1, src2) == ("vault-new", "vault") and first == second


@pytest.fixture
def client(sqlite_db, fake_redis, monkeypatch):
    monkeypatch.setattr("app.main.settings.enable_consumer", False)
    monkeypatch.setattr("app.main.aioredis.from_url", lambda *a, **k: fake_redis)
    with TestClient(app) as c:
        yield c


def test_register_login_me(client):
    r = client.post("/auth/register", json={"username": "alice", "password": "password123"})
    assert r.status_code == 201 and r.json()["username"] == "alice"
    assert client.post("/auth/register", json={"username": "alice", "password": "password123"}).status_code == 409
    assert client.post("/auth/register", json={"username": "a", "password": "short"}).status_code == 422

    assert client.post("/auth/login", json={"username": "alice", "password": "wrong-pass"}).status_code == 401
    token = client.post("/auth/login", json={"username": "alice", "password": "password123"}).json()["access_token"]
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["username"] == "alice"


def test_protected_endpoints_require_login(client):
    assert client.get("/strategies").status_code == 401
    assert client.get("/orders").status_code == 401
    assert (
        client.post("/timemachine/sessions", json={"symbol": "005930", "start_date": "2024-06-03"}).status_code == 401
    )
    assert client.get("/market/prices").status_code == 200  # 시세는 공개
    assert client.get("/anomalies").status_code == 200


def test_users_cannot_see_each_others_data(client):
    login(client, "alice")
    sid = client.post("/strategies", json={"name": "A", "symbol": "005930", "side": "buy", "conditions": RSI}).json()[
        "id"
    ]
    tm = client.post("/timemachine/sessions", json={"symbol": "005930", "start_date": "2024-06-03"}).json()["id"]

    login(client, "bob")
    assert client.get("/strategies").json() == []
    assert client.get(f"/strategies/{sid}").status_code == 404
    assert client.delete(f"/strategies/{sid}").status_code == 404
    assert client.get(f"/timemachine/sessions/{tm}").status_code == 404

    login(client, "alice")
    assert len(client.get("/strategies").json()) == 1


def test_alert_list_filtering(client, fake_redis):
    import asyncio
    import json

    async def seed():
        for a in (
            {"type": "order", "user_id": 1, "message": "alice 주문"},
            {"type": "order", "user_id": 2, "message": "bob 주문"},
            {"type": "anomaly", "message": "이상거래"},
        ):
            await fake_redis.lpush("alerts", json.dumps(a))

    asyncio.run(seed())
    assert [a["message"] for a in client.get("/alerts").json()] == ["이상거래"]
    login(client, "alice")  # user_id 1
    assert {a["message"] for a in client.get("/alerts").json()} == {"이상거래", "alice 주문"}


def test_migration_adds_user_id_to_existing_tables(tmp_path):
    """user_id 컬럼이 없던 예전 DB(기존 도커 볼륨)도 시작할 때 컬럼이 추가돼야 한다"""
    from sqlalchemy import create_engine, inspect, text

    from app import db

    url = f"sqlite:///{tmp_path}/old.db"
    old = create_engine(url)
    with old.begin() as c:
        c.execute(
            text(
                "CREATE TABLE strategies (id INTEGER PRIMARY KEY, name VARCHAR(100), symbol VARCHAR(20), "
                "side VARCHAR(4), conditions JSON, quantity INTEGER, cooldown_sec INTEGER, enabled BOOLEAN, "
                "created_at DATETIME)"
            )
        )
        c.execute(
            text("INSERT INTO strategies (name, symbol, side, conditions) VALUES ('옛 전략', '005930', 'buy', '[]')")
        )
    db.configure(url)
    db.init_db(retries=1)
    cols = {c["name"] for c in inspect(db.engine).get_columns("strategies")}
    assert "user_id" in cols
    with db.engine.connect() as c:
        assert c.execute(text("SELECT name FROM strategies")).scalar() == "옛 전략"  # 기존 데이터 유지
    db.engine = None
