"""자동매매 엔진

새 시세가 들어올 때마다(consumer에서 호출) 해당 종목의 활성 전략을 평가하고,
조건을 만족하면 모의 주문을 실행한 뒤 알림을 Redis에 남긴다.

Redis 사용
- ticks:<종목>      최근 시세 → 지표 계산 입력
- cooldown:<전략ID> 같은 전략이 연속으로 주문하지 않도록 쿨다운 (SET NX EX)
- alerts            최근 알림 목록 + Pub/Sub 채널 (실시간 알림, Issue #15)
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app import db
from app.market.cache import get_ticks
from app.strategy.broker import FILLED, SUBMITTED, Broker, PaperBroker
from app.strategy.evaluator import evaluate
from app.strategy.models import Strategy
from app.trading import broker as kiwoom_broker

log = logging.getLogger("uvicorn.error")

ALERTS_KEY = "alerts"
MAX_ALERTS = 100
broker: Broker = PaperBroker()  # account="paper" 전략용. 다른 Broker로 바꿔도 엔진 코드는 그대로


def _load_strategies(symbol: str) -> list[Strategy]:
    with db.new_session() as s:
        return list(s.scalars(select(Strategy).where(Strategy.symbol == symbol, Strategy.enabled.is_(True))))


def _place(strategy_id: int, price: float, reason: dict) -> dict:
    with db.new_session() as s:
        strategy = s.get(Strategy, strategy_id)
        order = broker.place(s, strategy, price, reason)
        return {
            "order_id": order.id,
            "user_id": order.user_id,
            "strategy_id": strategy.id,
            "strategy_name": strategy.name,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "price": order.price,
            "status": order.status,
            "reject_reason": order.reason.get("reject_reason", ""),
        }


def order_message(strategy_name: str, stock_name: str, order: dict) -> str:
    """주문 결과(체결·접수·거부)에 맞는 알림 문장"""
    side = "매수" if order["side"] == "buy" else "매도"
    head = f"[{strategy_name}] {stock_name} {order['quantity']}주 {side}"
    if order["status"] == FILLED:
        return f"{head} @ {order['price']:,.0f}원"
    if order["status"] == SUBMITTED:
        return f"{head} 주문 접수 @ {order['price']:,.0f}원"
    return f"{head} 주문 거부: {order['reject_reason']}"


async def push_alert(r, alert: dict) -> None:
    data = json.dumps(alert, ensure_ascii=False)
    pipe = r.pipeline()
    pipe.lpush(ALERTS_KEY, data)
    pipe.ltrim(ALERTS_KEY, 0, MAX_ALERTS - 1)
    pipe.publish(ALERTS_KEY, data)
    await pipe.execute()


async def on_tick(r, tick: dict) -> list[dict]:
    """시세 1건 처리. 이번에 낸 주문 결과 목록(거부 포함)을 반환한다."""
    strategies = await asyncio.to_thread(_load_strategies, tick["symbol"])
    if not strategies:
        return []

    closes = [t["price"] for t in await get_ticks(r, tick["symbol"], limit=300)]
    executed = []
    for st in strategies:
        ok, details = evaluate(st.conditions, closes)
        if not ok:
            continue
        # 쿨다운 중이면 건너뜀 (Redis 키가 없을 때만 SET 성공)
        if st.cooldown_sec > 0 and not await r.set(f"cooldown:{st.id}", 1, nx=True, ex=st.cooldown_sec):
            continue

        side_kr = "매수" if st.side == "buy" else "매도"
        if st.account == "kiwoom":  # 사용자 키움 계좌로 실제 주문 (위험 제한 포함)
            order = await kiwoom_broker.place_order(
                r, st.user_id, st.symbol, st.side, st.quantity, tick["price"],
                strategy_id=st.id, strategy_name=st.name, reason={"conditions": details},
            )
            label = {"SUBMITTED": "키움 주문 접수", "BLOCKED": "키움 주문 차단", "REJECTED": "키움 주문 거부"}
            message = (f"[{st.name}] {label.get(order['status'], order['status'])}: {tick['name']} {st.quantity}주 "
                       f"{side_kr} ({order['message']})")
        else:  # 자체 모의 체결 (Broker 인터페이스)
            order = await asyncio.to_thread(_place, st.id, tick["price"], {"conditions": details})
            message = order_message(st.name, tick["name"], order)
        alert = {
            "type": "order",
            "user_id": order["user_id"],  # 주문 알림은 전략 주인에게만 전달
            "message": message,
            "order": order,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await push_alert(r, alert)
        log.info(alert["message"])
        executed.append(order)
    return executed
