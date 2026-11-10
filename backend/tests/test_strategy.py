import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.market.cache import save_tick
from app.market.sources import make_tick
from app.strategy.engine import ALERTS_KEY, on_tick
from app.strategy.evaluator import evaluate, evaluate_condition
from app.strategy.indicators import compute, snapshot
from tests.conftest import login

RISING = np.arange(100, 140, dtype=float)  # 계속 오르는 가격
FALLING = RISING[::-1].copy()


# ---------- 지표 ----------
def test_sma():
    assert compute("SMA", [1, 2, 3, 4, 5], 5)[-1] == 3


def test_rsi_extremes():
    assert compute("RSI", RISING, 14)[-1] == pytest.approx(100)
    assert compute("RSI", FALLING, 14)[-1] == pytest.approx(0)


def test_bollinger_order():
    closes = 100 + np.sin(np.arange(60))
    upper, mid, lower = (compute(n, closes)[-1] for n in ("BB_UPPER", "BB_MIDDLE", "BB_LOWER"))
    assert upper > mid > lower


def test_snapshot_handles_short_data():
    snap = snapshot([100, 101, 102])
    assert snap["price"] == 102 and snap["sma20"] is None


# ---------- 조건 평가 ----------
def test_number_condition():
    cond = {"left": {"name": "RSI", "period": 14}, "op": "<", "right": 30}
    assert evaluate_condition(cond, FALLING)[0] is True
    assert evaluate_condition(cond, RISING)[0] is False


def test_cross_up():
    # 하락하다가 마지막에 급등 → 현재가가 5일 이평선을 상향 돌파
    closes = np.concatenate([FALLING, [FALLING[-1] + 20]])
    cond = {"left": {"name": "PRICE"}, "op": "cross_up", "right": {"name": "SMA", "period": 5}}
    assert evaluate_condition(cond, closes)[0] is True
    assert evaluate_condition(cond, RISING)[0] is False  # 이미 위에 있으면 돌파 아님


def test_not_enough_data():
    ok, details = evaluate([{"left": {"name": "SMA", "period": 20}, "op": ">", "right": 0}], [100, 101])
    assert ok is False and details[0]["reason"] == "데이터 부족"


def test_all_conditions_must_pass():
    conds = [
        {"left": {"name": "PRICE"}, "op": ">", "right": 0},
        {"left": {"name": "PRICE"}, "op": ">", "right": 1_000_000},
    ]
    assert evaluate(conds, RISING)[0] is False


# ---------- 엔진 ----------
async def _feed(r, prices, symbol="005930"):
    for p in prices:
        await save_tick(r, make_tick(symbol, "삼성전자", p, 100, 500, 500))
    return make_tick(symbol, "삼성전자", prices[-1], 100, 500, 500)


def _create(client, **over):
    body = {
        "name": "RSI 과매도 매수",
        "symbol": "005930",
        "side": "buy",
        "conditions": [{"left": {"name": "RSI", "period": 14}, "op": "<", "right": 30}],
        "quantity": 10,
        "cooldown_sec": 60,
        **over,
    }
    res = client.post("/strategies", json=body)
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture
def client(sqlite_db, fake_redis, monkeypatch):
    monkeypatch.setattr("app.main.settings.enable_consumer", False)
    monkeypatch.setattr("app.main.aioredis.from_url", lambda *a, **k: fake_redis)
    with TestClient(app) as c:
        login(c)
        yield c


@pytest.mark.asyncio
async def test_engine_places_order_and_respects_cooldown(sqlite_db, fake_redis):
    from app import db
    from app.strategy.models import Strategy

    with db.new_session() as s:
        s.add(Strategy(name="RSI 과매도", symbol="005930", side="buy", quantity=10, cooldown_sec=60, user_id=1,
                       conditions=[{"left": {"name": "RSI", "period": 14}, "op": "<", "right": 30}]))
        s.commit()

    tick = await _feed(fake_redis, FALLING)
    orders = await on_tick(fake_redis, tick)
    assert len(orders) == 1 and orders[0]["quantity"] == 10

    assert await on_tick(fake_redis, tick) == []  # 쿨다운 중
    alerts = await fake_redis.lrange(ALERTS_KEY, 0, -1)
    assert len(alerts) == 1 and "매수" in alerts[0]


@pytest.mark.asyncio
async def test_engine_ignores_disabled_and_other_symbols(sqlite_db, fake_redis):
    from app import db
    from app.strategy.models import Strategy

    cond = [{"left": {"name": "PRICE"}, "op": ">", "right": 0}]
    with db.new_session() as s:
        s.add(Strategy(name="꺼진 전략", symbol="005930", side="buy", conditions=cond, enabled=False))
        s.add(Strategy(name="다른 종목", symbol="000660", side="buy", conditions=cond))
        s.commit()

    tick = await _feed(fake_redis, RISING)
    assert await on_tick(fake_redis, tick) == []


# ---------- API ----------
def test_strategy_crud(client):
    st = _create(client)
    assert client.get("/strategies").json()[0]["name"] == "RSI 과매도 매수"

    st["enabled"] = False
    body = {k: v for k, v in st.items() if k not in ("id", "created_at")}
    assert client.put(f"/strategies/{st['id']}", json=body).json()["enabled"] is False

    assert client.delete(f"/strategies/{st['id']}").status_code == 204
    assert client.get(f"/strategies/{st['id']}").status_code == 404


def test_strategy_validation(client):
    res = client.post("/strategies", json={"name": "x", "symbol": "005930", "side": "hold", "conditions": []})
    assert res.status_code == 422


def test_orders_alerts_indicators_api(client, fake_redis):
    import asyncio

    _create(client, conditions=[{"left": {"name": "PRICE"}, "op": ">", "right": 0}], cooldown_sec=0)

    async def run():
        tick = await _feed(fake_redis, RISING)
        await on_tick(fake_redis, tick)

    asyncio.run(run())

    orders = client.get("/orders").json()
    assert len(orders) == 1 and orders[0]["price"] == RISING[-1]
    assert client.get("/alerts").json()[0]["type"] == "order"

    ind = client.get("/indicators/005930").json()
    assert ind["count"] == len(RISING) and ind["rsi14"] == pytest.approx(100)


def test_anomalies_api(client, fake_redis):
    import asyncio
    import json

    async def seed():
        for sym in ("005930", "000660"):
            await fake_redis.lpush("anomalies", json.dumps({"symbol": sym, "message": "test"}))

    asyncio.run(seed())
    assert len(client.get("/anomalies").json()) == 2
    assert [a["symbol"] for a in client.get("/anomalies?symbol=005930").json()] == ["005930"]
