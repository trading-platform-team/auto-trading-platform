from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_health_deps_returns_all_services():
    res = client.get("/health/deps")
    assert res.status_code == 200
    body = res.json()
    assert set(body["deps"]) == {"kafka", "redis", "postgres", "vault", "ai"}
    assert body["status"] in {"ok", "degraded"}
