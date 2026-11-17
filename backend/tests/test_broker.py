"""Broker 인터페이스: 어떤 Broker를 끼워도 엔진이 같은 방식으로 주문·알림을 처리하는지"""

import json

import pytest

from app import db
from app.market.cache import save_tick
from app.market.sources import make_tick
from app.strategy import engine
from app.strategy.broker import FILLED, PENDING, REJECTED, Broker, PaperBroker
from app.strategy.engine import ALERTS_KEY, on_tick
from app.strategy.models import Order, Strategy

ALWAYS = [{"left": {"name": "PRICE"}, "op": ">", "right": 0}]  # 항상 만족하는 조건


class RejectBroker(Broker):
    name = "reject"

    def place(self, session, strategy, price, reason):
        return self.record(session, strategy, price, reason, REJECTED, "현금이 부족해요")


class PendingBroker(Broker):
    name = "pending"

    def place(self, session, strategy, price, reason):
        return self.record(session, strategy, price, reason, PENDING)


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
async def test_engine_alert_for_pending_and_filled(sqlite_db, fake_redis, monkeypatch):
    _strategy()
    monkeypatch.setattr(engine, "broker", PendingBroker())
    await on_tick(fake_redis, await _tick(fake_redis))
    assert json.loads(await fake_redis.lindex(ALERTS_KEY, 0))["message"].endswith("주문 접수 @ 70,000원")

    monkeypatch.setattr(engine, "broker", PaperBroker())
    orders = await on_tick(fake_redis, await _tick(fake_redis, 71000))
    assert orders[0]["status"] == FILLED
    assert json.loads(await fake_redis.lindex(ALERTS_KEY, 0))["message"] == "[테스트] 삼성전자 3주 매수 @ 71,000원"
