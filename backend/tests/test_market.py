import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.market.cache import MAX_TICKS, get_latest, get_ticks, save_tick
from app.market.sources import DEFAULT_SYMBOLS, MockSource, create_source

REQUIRED_FIELDS = {"symbol", "name", "price", "volume", "bid_size", "ask_size", "timestamp"}


def test_mock_source_generates_tick_for_every_symbol():
    ticks = MockSource(seed=1).next_ticks()
    assert {t["symbol"] for t in ticks} == set(DEFAULT_SYMBOLS)
    for t in ticks:
        assert REQUIRED_FIELDS <= t.keys()
        assert t["price"] > 0 and t["volume"] > 0


def test_mock_source_injects_anomalies():
    src = MockSource(anomaly_rate=1.0, seed=7)
    ticks = [t for _ in range(20) for t in src.next_ticks()]
    assert max(t["volume"] for t in ticks) >= 250  # 거래량 급증 이벤트 포함


def test_unknown_source():
    with pytest.raises(ValueError):
        create_source("nope")


@pytest.mark.asyncio
async def test_cache_save_and_read():
    r = fakeredis.FakeAsyncRedis(decode_responses=True)
    src = MockSource(seed=3)
    for _ in range(5):
        for t in src.next_ticks():
            await save_tick(r, t)

    latest = await get_latest(r)
    assert len(latest) == len(DEFAULT_SYMBOLS)

    ticks = await get_ticks(r, "005930", limit=3)
    assert len(ticks) == 3
    assert ticks[0]["timestamp"] <= ticks[-1]["timestamp"]  # 오래된 → 최신 순


@pytest.mark.asyncio
async def test_cache_keeps_only_recent_ticks():
    r = fakeredis.FakeAsyncRedis(decode_responses=True)
    src = MockSource(symbols={"005930": ("삼성전자", 70000)}, seed=4)
    for _ in range(MAX_TICKS + 20):
        await save_tick(r, src.next_ticks()[0])
    assert len(await get_ticks(r, "005930", limit=1000)) == MAX_TICKS


def test_market_api(monkeypatch):
    monkeypatch.setattr("app.main.settings.enable_consumer", False)
    fake = fakeredis.FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr("app.main.aioredis.from_url", lambda *a, **k: fake)

    with TestClient(app) as client:
        assert client.get("/market/prices").json() == []
