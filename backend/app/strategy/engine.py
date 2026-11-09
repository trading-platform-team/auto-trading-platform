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
from app.strategy.broker import PaperBroker
from app.strategy.evaluator import evaluate
from app.strategy.models import Strategy

log = logging.getLogger("uvicorn.error")

ALERTS_KEY = "alerts"
MAX_ALERTS = 100
broker = PaperBroker()


def _load_strategies(symbol: str) -> list[Strategy]:
    with db.new_session() as s:
        return list(s.scalars(select(Strategy).where(Strategy.symbol == symbol, Strategy.enabled.is_(True))))


def _place(strategy_id: int, price: float, reason: dict) -> dict:
    with db.new_session() as s:
        strategy = s.get(Strategy, strategy_id)
        order = broker.place(s, strategy, price, reason)
        return {
            "order_id": order.id,
            "strategy_id": strategy.id,
            "strategy_name": strategy.name,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "price": order.price,
        }


async def push_alert(r, alert: dict) -> None:
    data = json.dumps(alert, ensure_ascii=False)
    pipe = r.pipeline()
    pipe.lpush(ALERTS_KEY, data)
    pipe.ltrim(ALERTS_KEY, 0, MAX_ALERTS - 1)
    pipe.publish(ALERTS_KEY, data)
    await pipe.execute()


async def on_tick(r, tick: dict) -> list[dict]:
    """시세 1건 처리. 실행된 주문 목록을 반환한다."""
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

        order = await asyncio.to_thread(_place, st.id, tick["price"], {"conditions": details})
        alert = {
            "type": "order",
            "message": f"[{st.name}] {tick['name']} {st.quantity}주 {'매수' if st.side == 'buy' else '매도'} "
            f"@ {tick['price']:,}원",
            "order": order,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await push_alert(r, alert)
        log.info(alert["message"])
        executed.append(order)
    return executed
