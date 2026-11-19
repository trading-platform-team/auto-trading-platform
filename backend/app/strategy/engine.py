"""자동매매 엔진

새 시세가 들어올 때마다(consumer에서 호출) 해당 종목의 활성 전략을 평가하고,
조건을 만족하면 모의 주문을 실행한 뒤 알림을 Redis에 남긴다.
모의 매수 전략에 익절·손절(%)이 있으면, 이 전략이 산 주식이 평균 단가 대비
그만큼 오르거나 내렸을 때 먼저 매도한다 (그 시세에서는 매수 조건을 보지 않음).
모의 매수 전략은 자기가 산 주식이 남아 있는 동안 다시 사지 않는다 (백테스트와 같은
한 번에 한 포지션). 조건이 계속 참이어도 쿨다운마다 물타기 매수가 쌓이지 않게 하기 위함.

Redis 사용
- ticks:<종목>      최근 시세 → 지표 계산 입력
- cooldown:<전략ID> 같은 전략이 연속으로 주문하지 않도록 쿨다운 (SET NX EX)
- exit:<전략ID>     익절·손절 매도가 거부될 때 매 시세마다 다시 시도하지 않도록 잠깐 막음
- alerts            최근 알림 목록 + Pub/Sub 채널 (실시간 알림, Issue #15)
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app import db
from app.market.cache import get_ticks
from app.strategy.broker import FILLED, SUBMITTED, Broker, PaperBroker, exit_reason, position
from app.strategy.evaluator import evaluate
from app.strategy.models import Strategy
from app.trading import broker as kiwoom_broker

log = logging.getLogger("uvicorn.error")

ALERTS_KEY = "alerts"
MAX_ALERTS = 100
broker: Broker = PaperBroker()  # account="paper" 전략용. 다른 Broker로 바꿔도 엔진 코드는 그대로
EXIT_RETRY_SEC = 30  # 익절·손절 매도가 거부됐을 때 다시 시도하기까지


def _load_strategies(symbol: str) -> list[Strategy]:
    with db.new_session() as s:
        return list(s.scalars(select(Strategy).where(Strategy.symbol == symbol, Strategy.enabled.is_(True))))


def _order_dict(strategy: Strategy, order) -> dict:
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
        "exit": order.reason.get("exit"),  # take_profit | stop_loss | None
        "exit_label": order.reason.get("exit_label"),
        "change_pct": order.reason.get("change_pct"),
    }


def _place(strategy_id: int, price: float, reason: dict) -> dict:
    with db.new_session() as s:
        strategy = s.get(Strategy, strategy_id)
        return _order_dict(strategy, broker.place(s, strategy, price, reason))


def uses_exit(st: Strategy) -> bool:
    return (
        isinstance(broker, PaperBroker)
        and st.account != "kiwoom"
        and st.side == "buy"
        and (st.take_profit_pct is not None or st.stop_loss_pct is not None)
    )


def holds_one_position(st: Strategy) -> bool:
    """보유 중이면 다시 사지 않는 전략인지 (모의 매수 전략)"""
    return isinstance(broker, PaperBroker) and st.account != "kiwoom" and st.side == "buy"


def _held(strategy_id: int) -> int:
    """이 전략이 사서 아직 남아 있는 수량"""
    with db.new_session() as s:
        strategy = s.get(Strategy, strategy_id)
        if strategy is None or strategy.user_id is None:
            return 0
        return broker.held_by_strategy(s, strategy)


def _check_exit(strategy_id: int, price: float) -> tuple[int, dict] | None:
    """익절·손절할 때면 (매도 수량, 사유), 아니면 None"""
    with db.new_session() as s:
        strategy = s.get(Strategy, strategy_id)
        if strategy is None or strategy.user_id is None:
            return None
        pos = position(s, strategy)
        qty = broker.held_by_strategy(s, strategy) if pos else 0
        if qty == 0:
            return None
        reason = exit_reason(strategy, pos.avg_price, price)
        return (qty, reason) if reason else None


def _close(strategy_id: int, price: float, quantity: int, reason: dict) -> dict:
    with db.new_session() as s:
        strategy = s.get(Strategy, strategy_id)
        return _order_dict(strategy, broker.close(s, strategy, price, quantity, reason))


def order_message(strategy_name: str, stock_name: str, order: dict) -> str:
    """주문 결과(체결·접수·거부)에 맞는 알림 문장"""
    side = "매수" if order["side"] == "buy" else "매도"
    if order.get("exit_label"):  # 익절·손절 매도
        side = f"{order['exit_label']} 매도 ({order['change_pct']:+.2f}%)"
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
        if st.account == "kiwoom" and tick.get("source") != "kiwoom":
            continue  # 실제 돈 주문은 키움 실시간 시세로만 (가상 시세·과거 분봉 재생으로 주문하지 않음)
        if uses_exit(st):
            found = await asyncio.to_thread(_check_exit, st.id, tick["price"])
            if found:
                if not await r.set(f"exit:{st.id}", 1, nx=True, ex=EXIT_RETRY_SEC):
                    continue  # 방금 매도가 거부돼 잠시 쉬는 중
                qty, reason = found
                order = await asyncio.to_thread(_close, st.id, tick["price"], qty, reason)
                if order["status"] == FILLED:
                    await r.delete(f"exit:{st.id}")
                await _alert(r, order, order_message(st.name, tick["name"], order))
                executed.append(order)
                continue  # 매도한 시세에서는 다시 사지 않음

        if holds_one_position(st) and await asyncio.to_thread(_held, st.id) > 0:
            continue  # 이미 산 주식이 남아 있음 (익절·손절·매도 전략·직접 매도로 정리된 뒤에 다시 매수)

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
        await _alert(r, order, message)
        executed.append(order)
    return executed


async def _alert(r, order: dict, message: str) -> None:
    alert = {
        "type": "order",
        "user_id": order["user_id"],  # 주문 알림은 전략 주인에게만 전달
        "message": message,
        "order": order,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await push_alert(r, alert)
    log.info(message)
