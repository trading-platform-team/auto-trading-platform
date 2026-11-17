"""실시간 엔진 익절·손절: 모의 매수 전략이 산 주식을 평균 단가 대비 등락률로 매도"""

import json

import pytest
from pydantic import ValidationError

from app import db
from app.edu import account
from app.edu.models import EduPosition, EduTrade
from app.market.cache import save_tick
from app.market.sources import make_tick
from app.strategy.broker import FILLED, REJECTED, PaperBroker, exit_reason
from app.strategy.engine import ALERTS_KEY, on_tick
from app.strategy.models import Order, Strategy
from app.strategy.schemas import StrategyIn

ALWAYS = [{"left": {"name": "PRICE"}, "op": ">", "right": 0}]  # 항상 만족하는 매수 조건


def _strategy(take_profit=5.0, stop_loss=3.0, quantity=3) -> int:
    with db.new_session() as s:
        st = Strategy(
            user_id=1,
            name="익절손절",
            symbol="005930",
            side="buy",
            conditions=ALWAYS,
            quantity=quantity,
            cooldown_sec=0,
            take_profit_pct=take_profit,
            stop_loss_pct=stop_loss,
        )
        s.add(st)
        s.commit()
        return st.id


async def _tick(r, price):
    for _ in range(2):  # 조건 평가에는 시세가 2개 이상 필요
        tick = make_tick("005930", "삼성전자", price, 100, 500, 500)
        await save_tick(r, tick)
    return tick


def _held() -> int:
    with db.new_session() as s:
        pos = s.query(EduPosition).filter_by(user_id=1, symbol="005930").one_or_none()
        return pos.quantity if pos else 0


@pytest.mark.asyncio
async def test_take_profit_sells_strategy_shares(sqlite_db, fake_redis):
    _strategy()
    assert (await on_tick(fake_redis, await _tick(fake_redis, 70000)))[0]["side"] == "buy"
    assert _held() == 3

    orders = await on_tick(fake_redis, await _tick(fake_redis, 74000))  # +5.71%
    assert len(orders) == 1  # 매도한 시세에서는 다시 사지 않음
    o = orders[0]
    assert o["side"] == "sell" and o["status"] == FILLED and o["quantity"] == 3 and o["exit"] == "take_profit"
    assert _held() == 0

    alert = json.loads(await fake_redis.lindex(ALERTS_KEY, 0))
    assert alert["message"] == "[익절손절] 삼성전자 3주 익절 매도 (+5.71%) @ 74,000원"
    with db.new_session() as s:
        sell = s.query(EduTrade).filter_by(side="sell").one()
        assert sell.strategy_id is not None and sell.realized_pnl > 0
        saved = s.query(Order).filter_by(side="sell").one()
        assert saved.reason["exit"] == "take_profit" and saved.reason["trade_id"] == sell.id


@pytest.mark.asyncio
async def test_stop_loss_sells(sqlite_db, fake_redis):
    _strategy()
    await on_tick(fake_redis, await _tick(fake_redis, 70000))
    o = (await on_tick(fake_redis, await _tick(fake_redis, 67900)))[0]  # -3.00%
    assert o["side"] == "sell" and o["exit"] == "stop_loss" and o["change_pct"] == -3.0
    assert _held() == 0


@pytest.mark.asyncio
async def test_no_exit_between_thresholds_keeps_buying(sqlite_db, fake_redis):
    _strategy()
    await on_tick(fake_redis, await _tick(fake_redis, 70000))
    o = (await on_tick(fake_redis, await _tick(fake_redis, 71000)))[0]  # +1.43%
    assert o["side"] == "buy" and _held() == 6


@pytest.mark.asyncio
async def test_exit_sells_only_what_strategy_bought(sqlite_db, fake_redis):
    """직접 주문으로 산 주식은 남겨 둔다"""
    with db.new_session() as s:
        account.place_order(s, 1, "005930", "buy", 10, 70000)
    _strategy()
    await on_tick(fake_redis, await _tick(fake_redis, 70000))
    assert _held() == 13
    o = (await on_tick(fake_redis, await _tick(fake_redis, 74000)))[0]
    assert o["side"] == "sell" and o["quantity"] == 3
    assert _held() == 10


@pytest.mark.asyncio
async def test_exit_limited_by_manual_sell(sqlite_db, fake_redis):
    """전략이 산 주식을 직접 일부 팔았다면 남은 수량까지만 판다"""
    _strategy()
    await on_tick(fake_redis, await _tick(fake_redis, 70000))
    with db.new_session() as s:
        account.place_order(s, 1, "005930", "sell", 2, 70000)
    o = (await on_tick(fake_redis, await _tick(fake_redis, 74000)))[0]
    assert o["quantity"] == 1 and _held() == 0


@pytest.mark.asyncio
async def test_rejected_exit_is_not_retried_every_tick(sqlite_db, fake_redis, monkeypatch):
    _strategy()
    await on_tick(fake_redis, await _tick(fake_redis, 70000))

    def reject(self, session, strategy, price, quantity, reason):
        return self.record(session, strategy, price, reason, REJECTED, "테스트 거부", side="sell", quantity=quantity)

    monkeypatch.setattr(PaperBroker, "close", reject)
    first = await on_tick(fake_redis, await _tick(fake_redis, 74000))
    assert first[0]["status"] == REJECTED
    assert await on_tick(fake_redis, await _tick(fake_redis, 74000)) == []  # 잠시 쉬는 중 (매수도 하지 않음)


@pytest.mark.asyncio
async def test_strategy_without_exit_does_not_sell(sqlite_db, fake_redis):
    _strategy(take_profit=None, stop_loss=None)
    await on_tick(fake_redis, await _tick(fake_redis, 70000))
    o = (await on_tick(fake_redis, await _tick(fake_redis, 90000)))[0]
    assert o["side"] == "buy"


def test_exit_reason_thresholds():
    st = Strategy(take_profit_pct=5.0, stop_loss_pct=3.0)
    assert exit_reason(st, 100, 104.9) is None
    assert exit_reason(st, 100, 105)["exit"] == "take_profit"
    assert exit_reason(st, 100, 97)["exit"] == "stop_loss"
    assert exit_reason(Strategy(take_profit_pct=5.0), 100, 50) is None  # 손절 미설정


def _body(**kw):
    return {"name": "x", "symbol": "005930", "side": "buy", "conditions": ALWAYS, **kw}


def test_schema_exit_only_for_paper_buy():
    assert StrategyIn(**_body(take_profit_pct=5, stop_loss_pct=3)).stop_loss_pct == 3
    with pytest.raises(ValidationError, match="매수 전략"):
        StrategyIn(**_body(side="sell", take_profit_pct=5))
    with pytest.raises(ValidationError, match="모의 주문"):
        StrategyIn(**_body(account="kiwoom", stop_loss_pct=3))
    with pytest.raises(ValidationError):
        StrategyIn(**_body(stop_loss_pct=100))  # 100% 이상 손절은 의미 없음
    assert StrategyIn(**_body(side="sell")).take_profit_pct is None


def test_migration_adds_exit_columns(tmp_path):
    from sqlalchemy import create_engine, inspect, text

    url = f"sqlite:///{tmp_path}/old.db"
    with create_engine(url).begin() as c:
        c.execute(
            text(
                "CREATE TABLE strategies (id INTEGER PRIMARY KEY, name VARCHAR(100), symbol VARCHAR(20), "
                "side VARCHAR(4), conditions JSON, quantity INTEGER, cooldown_sec INTEGER, enabled BOOLEAN, "
                "created_at DATETIME)"
            )
        )
    db.configure(url)
    db.init_db(retries=1)
    try:
        cols = {c["name"] for c in inspect(db.engine).get_columns("strategies")}
        assert {"take_profit_pct", "stop_loss_pct"} <= cols
    finally:
        db.engine = None
