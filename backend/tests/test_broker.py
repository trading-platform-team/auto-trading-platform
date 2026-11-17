"""Broker 인터페이스: 어떤 Broker를 끼워도 엔진이 같은 방식으로 주문·알림을 처리하는지"""

import json

import pytest

from app import db
from app.edu import account
from app.edu.models import EduPosition, EduTrade
from app.market.cache import save_tick
from app.market.sources import make_tick
from app.strategy import engine
from app.strategy.broker import FILLED, REJECTED, SUBMITTED, Broker, PaperBroker
from app.strategy.engine import ALERTS_KEY, on_tick
from app.strategy.models import Order, Strategy

ALWAYS = [{"left": {"name": "PRICE"}, "op": ">", "right": 0}]  # 항상 만족하는 조건


class RejectBroker(Broker):
    name = "reject"

    def place(self, session, strategy, price, reason):
        return self.record(session, strategy, price, reason, REJECTED, "현금이 부족해요")


class SubmittedBroker(Broker):
    name = "submitted"

    def place(self, session, strategy, price, reason):
        return self.record(session, strategy, price, reason, SUBMITTED)


def _strategy(user_id=1) -> int:
    with db.new_session() as s:
        st = Strategy(
            user_id=user_id, name="테스트", symbol="005930", side="buy", conditions=ALWAYS, quantity=3, cooldown_sec=0
        )
        s.add(st)
        s.commit()
        return st.id


async def _tick(r, price=70000):
    """조건 평가에는 시세가 2개 이상 필요하다"""
    for _ in range(2):
        tick = make_tick("005930", "삼성전자", price, 100, 500, 500)
        await save_tick(r, tick)
    return tick


def test_broker_is_abstract():
    with pytest.raises(TypeError):
        Broker()


def test_paper_broker_fills(sqlite_db):
    sid = _strategy()
    with db.new_session() as s:
        order = PaperBroker().place(s, s.get(Strategy, sid), 70000, {"conditions": []})
        assert order.id and order.status == FILLED and order.quantity == 3 and order.user_id == 1


def test_record_rejects_unknown_status(sqlite_db):
    sid = _strategy()
    with db.new_session() as s, pytest.raises(ValueError):
        Broker.record(s, s.get(Strategy, sid), 70000, {}, "DONE")


@pytest.mark.asyncio
async def test_engine_records_rejected_order_and_alerts(sqlite_db, fake_redis, monkeypatch):
    monkeypatch.setattr(engine, "broker", RejectBroker())
    _strategy()
    orders = await on_tick(fake_redis, await _tick(fake_redis))

    assert orders[0]["status"] == REJECTED and orders[0]["reject_reason"] == "현금이 부족해요"
    with db.new_session() as s:
        saved = s.query(Order).one()
        assert saved.status == REJECTED and saved.reason["reject_reason"] == "현금이 부족해요"
    alert = json.loads(await fake_redis.lindex(ALERTS_KEY, 0))
    assert alert["message"] == "[테스트] 삼성전자 3주 매수 주문 거부: 현금이 부족해요"


@pytest.mark.asyncio
async def test_engine_alert_for_submitted_and_filled(sqlite_db, fake_redis, monkeypatch):
    _strategy()
    monkeypatch.setattr(engine, "broker", SubmittedBroker())
    await on_tick(fake_redis, await _tick(fake_redis))
    assert json.loads(await fake_redis.lindex(ALERTS_KEY, 0))["message"].endswith("주문 접수 @ 70,000원")

    monkeypatch.setattr(engine, "broker", PaperBroker())
    orders = await on_tick(fake_redis, await _tick(fake_redis, 71000))
    assert orders[0]["status"] == FILLED
    assert json.loads(await fake_redis.lindex(ALERTS_KEY, 0))["message"] == "[테스트] 삼성전자 3주 매수 @ 71,000원"


# ---------- PaperBroker ↔ 가상계좌 ----------
def _place(sid: int, price: float = 70000):
    with db.new_session() as s:
        return PaperBroker().place(s, s.get(Strategy, sid), price, {"conditions": []})


def _set_side(sid: int, side: str, quantity: int | None = None) -> None:
    with db.new_session() as s:
        st = s.get(Strategy, sid)
        st.side = side
        if quantity is not None:
            st.quantity = quantity
        s.commit()


def test_paper_buy_uses_virtual_account(sqlite_db):
    sid = _strategy()
    order = _place(sid)
    assert order.status == FILLED
    with db.new_session() as s:
        trade = s.get(EduTrade, order.reason["trade_id"])
        assert trade.strategy_id == sid and trade.quantity == 3 and trade.price == 70000
        pos = s.query(EduPosition).filter_by(user_id=1, symbol="005930").one()
        assert pos.quantity == 3 and pos.avg_price == 70000
        cash = account.get_or_create(s, 1).cash
        assert cash == account.INITIAL_CASH - 70000 * 3 - trade.fee


def test_paper_buy_rejected_when_cash_short(sqlite_db):
    sid = _strategy()
    _set_side(sid, "buy", quantity=1000)  # 7천만 원 > 1천만 원
    order = _place(sid)
    assert order.status == REJECTED and "현금이 부족해요" in order.reason["reject_reason"]
    with db.new_session() as s:
        assert s.query(EduTrade).count() == 0  # 계좌는 그대로
        assert account.get_or_create(s, 1).cash == account.INITIAL_CASH
        assert s.query(Order).count() == 1  # 거부된 주문도 기록


def test_paper_sell_rejected_without_holdings(sqlite_db):
    sid = _strategy()
    _set_side(sid, "sell")
    order = _place(sid)
    assert order.status == REJECTED and "보유 수량이 부족해요" in order.reason["reject_reason"]


def test_paper_buy_then_sell_records_pnl(sqlite_db):
    sid = _strategy()
    _place(sid, 70000)
    _set_side(sid, "sell")
    order = _place(sid, 72000)
    assert order.status == FILLED
    with db.new_session() as s:
        trade = s.get(EduTrade, order.reason["trade_id"])
        assert trade.side == "sell" and trade.strategy_id == sid
        assert trade.realized_pnl == account.realized_pnl(70000, 72000, 3, trade.fee)
        assert s.query(EduPosition).count() == 0


def test_paper_rejects_strategy_without_owner(sqlite_db):
    sid = _strategy(user_id=None)
    order = _place(sid)
    assert order.status == REJECTED and "전략 주인" in order.reason["reject_reason"]


@pytest.mark.asyncio
async def test_engine_rejection_alert_from_virtual_account(sqlite_db, fake_redis):
    sid = _strategy()
    _set_side(sid, "sell")
    orders = await on_tick(fake_redis, await _tick(fake_redis))
    assert orders[0]["status"] == REJECTED
    alert = json.loads(await fake_redis.lindex(ALERTS_KEY, 0))
    assert alert["message"] == "[테스트] 삼성전자 3주 매도 주문 거부: 보유 수량이 부족해요. 지금 0주 가지고 있어요"


def test_migration_adds_strategy_id_to_edu_trades(tmp_path):
    """strategy_id 컬럼이 없던 예전 edu_trades 테이블에도 시작할 때 컬럼이 추가돼야 한다"""
    from sqlalchemy import create_engine, inspect, text

    url = f"sqlite:///{tmp_path}/old.db"
    old = create_engine(url)
    with old.begin() as c:
        c.execute(
            text(
                "CREATE TABLE edu_trades (id INTEGER PRIMARY KEY, user_id INTEGER, symbol VARCHAR(20), "
                "side VARCHAR(4), quantity INTEGER, price FLOAT, fee FLOAT, realized_pnl FLOAT, created_at DATETIME)"
            )
        )
        c.execute(
            text(
                "INSERT INTO edu_trades (user_id, symbol, side, quantity, price, fee) "
                "VALUES (1, '005930', 'buy', 1, 70000, 11)"
            )
        )
    db.configure(url)
    db.init_db(retries=1)
    try:
        assert "strategy_id" in {c["name"] for c in inspect(db.engine).get_columns("edu_trades")}
        with db.engine.connect() as c:
            assert c.execute(text("SELECT strategy_id FROM edu_trades")).scalar() is None  # 예전 거래 = 직접 주문
    finally:
        db.engine = None
