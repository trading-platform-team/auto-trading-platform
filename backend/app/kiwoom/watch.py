"""실시간 구독 대상 관리 (Redis)

전 종목을 실시간으로 받을 수는 없으므로, 지금 필요한 종목만 구독한다.
우선순위: 활성 전략 종목 > 기본 종목 > 사용자가 보고 있는 종목(최근 순)

- market:watch            (Sorted Set) 종목 → 만료 시각. 화면이 열려 있는 동안 /market/watch로 갱신
- market:strategy_symbols (Set)        활성 전략 종목. backend가 주기적으로 다시 계산
"""

import asyncio
import logging
import time

from sqlalchemy import select

log = logging.getLogger("uvicorn.error")

WATCH_KEY = "market:watch"
STRATEGY_KEY = "market:strategy_symbols"
WATCH_TTL_SEC = 90


async def touch(r, symbol: str, ttl: int = WATCH_TTL_SEC) -> None:
    await r.zadd(WATCH_KEY, {symbol: time.time() + ttl})


async def desired_symbols(r, defaults: list[str], limit: int) -> list[str]:
    now = time.time()
    await r.zremrangebyscore(WATCH_KEY, "-inf", now)
    watched = await r.zrevrange(WATCH_KEY, 0, -1)  # 최근에 본 종목이 앞
    strategy = sorted(await r.smembers(STRATEGY_KEY))
    out: list[str] = []
    for sym in [*strategy, *defaults, *watched]:
        if sym and sym not in out:
            out.append(sym)
    if len(out) > limit:
        log.warning("실시간 구독 상한(%d) 초과: %d개 중 %d개만 구독", limit, len(out), limit)
    return out[:limit]


def _strategy_symbols() -> list[str]:
    from app import db
    from app.strategy.models import Strategy

    with db.new_session() as s:
        return sorted(set(s.scalars(select(Strategy.symbol).where(Strategy.enabled.is_(True)))))


async def publish_strategy_symbols(r) -> list[str]:
    symbols = await asyncio.to_thread(_strategy_symbols)
    pipe = r.pipeline()
    pipe.delete(STRATEGY_KEY)
    if symbols:
        pipe.sadd(STRATEGY_KEY, *symbols)
    await pipe.execute()
    return symbols


async def publish_strategy_symbols_forever(r, interval: float = 5.0) -> None:
    while True:
        try:
            await publish_strategy_symbols(r)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("전략 종목 갱신 실패")
        await asyncio.sleep(interval)
