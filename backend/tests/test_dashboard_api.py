import asyncio
import json
import threading
import time

import fakeredis
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.market.cache import save_tick
from app.market.sources import make_tick


@pytest.fixture
def server():
    return fakeredis.FakeServer()


@pytest.fixture
def client(sqlite_db, server, monkeypatch):
    monkeypatch.setattr("app.main.settings.enable_consumer", False)
    monkeypatch.setattr(
        "app.main.aioredis.from_url", lambda *a, **k: fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    )
    with TestClient(app) as c:
        yield c


def test_chart_series(client, server):
    r = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)

    async def feed():
        for p in 100 + np.sin(np.arange(60)) * 5:
            await save_tick(r, make_tick("005930", "삼성전자", p, 100, 500, 500))

    asyncio.run(feed())
    rows = client.get("/market/chart/005930?limit=30").json()
    assert len(rows) == 30
    last = rows[-1]
    assert {"price", "sma5", "sma20", "bb_upper", "bb_lower", "rsi"} <= last.keys()
    assert last["bb_upper"] > last["bb_lower"] and 0 <= last["rsi"] <= 100
    assert client.get("/market/chart/000000").json() == []


def test_alerts_websocket(client, server):
    pub = fakeredis.FakeRedis(server=server, decode_responses=True)

    def publish_later():
        time.sleep(0.3)
        pub.publish("alerts", json.dumps({"type": "order", "message": "테스트 주문"}))

    with client.websocket_connect("/ws/alerts") as ws:
        threading.Thread(target=publish_later).start()
        assert json.loads(ws.receive_text())["message"] == "테스트 주문"
