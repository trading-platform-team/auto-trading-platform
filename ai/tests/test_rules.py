from fastapi.testclient import TestClient

from anomaly.rules import Bar, detect
from service import app


def _normal_bars(n=10):
    return [Bar(f"t{i}", 10000, 100, 500, 500) for i in range(n)]


def test_normal_data_has_no_anomaly():
    assert detect(_normal_bars()) == []


def test_volume_spike():
    bars = _normal_bars() + [Bar("spike", 10000, 1000, 500, 500)]
    types = [a.type for a in detect(bars)]
    assert "volume_spike" in types


def test_price_jump():
    bars = _normal_bars() + [Bar("jump", 10500, 100, 500, 500)]  # +5%
    found = [a for a in detect(bars) if a.type == "price_jump"]
    assert found and found[0].value == 5.0


def test_orderbook_imbalance():
    bars = [Bar("imb", 10000, 100, 900, 100)]
    found = [a for a in detect(bars) if a.type == "orderbook_imbalance"]
    assert found and found[0].value == 0.8


def test_detect_api(monkeypatch):
    monkeypatch.setenv("ENABLE_STREAM", "false")
    client = TestClient(app)
    body = {"bars": [{"timestamp": "a", "price": 100, "volume": 1},
                     {"timestamp": "b", "price": 110, "volume": 1}]}
    res = client.post("/detect", json=body)
    assert res.status_code == 200
    assert res.json()["anomalies"][0]["type"] == "price_jump"
