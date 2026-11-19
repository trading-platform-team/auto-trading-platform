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


def test_market_api(monkeypatch, sqlite_db):
    monkeypatch.setattr("app.main.settings.enable_consumer", False)
    fake = fakeredis.FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr("app.main.aioredis.from_url", lambda *a, **k: fake)

    with TestClient(app) as client:
        assert client.get("/market/prices").json() == []


class _Quotes:
    async def quotes(self, codes):
        return {c: {"symbol": c, "name": "에코프로", "price": 95000} for c in codes if c == "086520"}


@pytest.mark.asyncio
async def test_mock_source_adds_enabled_strategy_symbols(fake_redis):
    """기본 종목이 아닌 종목으로 만든 전략도 가상 시세가 생겨서 돈다"""
    from app.kiwoom.watch import STRATEGY_KEY

    src = MockSource(seed=5, redis=fake_redis, stocks=_Quotes())
    await fake_redis.sadd(STRATEGY_KEY, "086520", "999999", "005930")
    await src.sync()
    ticks = {t["symbol"]: t for t in src.next_ticks()}
    assert set(ticks) == set(DEFAULT_SYMBOLS) | {"086520", "999999"}
    assert ticks["086520"]["name"] == "에코프로" and abs(ticks["086520"]["price"] - 95000) < 95000 * 0.1
    assert ticks["999999"]["name"] == "999999"  # 현재가를 모르면 시작가로

    await fake_redis.delete(STRATEGY_KEY)  # 전략을 끄면 빠지고, 기본 종목은 남는다
    await src.sync()
    assert {t["symbol"] for t in src.next_ticks()} == set(DEFAULT_SYMBOLS)


@pytest.mark.asyncio
async def test_mock_source_without_redis_keeps_defaults():
    src = MockSource(seed=6)
    await src.sync()
    assert {t["symbol"] for t in src.next_ticks()} == set(DEFAULT_SYMBOLS)
