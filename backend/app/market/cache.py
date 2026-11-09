"""Redis 시세 캐시

- price:latest  (Hash)  종목코드 → 최신 시세 JSON
- ticks:<종목>  (List)  최근 시세 N개 (최신이 앞)
"""

import json

LATEST_KEY = "price:latest"
TICKS_KEY = "ticks:{symbol}"
MAX_TICKS = 300


async def save_tick(r, tick: dict) -> None:
    data = json.dumps(tick, ensure_ascii=False)
    key = TICKS_KEY.format(symbol=tick["symbol"])
    pipe = r.pipeline()
    pipe.hset(LATEST_KEY, tick["symbol"], data)
    pipe.lpush(key, data)
    pipe.ltrim(key, 0, MAX_TICKS - 1)
    await pipe.execute()


async def get_latest(r) -> list[dict]:
    raw = await r.hgetall(LATEST_KEY)
    return sorted((json.loads(v) for v in raw.values()), key=lambda t: t["symbol"])


async def get_ticks(r, symbol: str, limit: int = 50) -> list[dict]:
    raw = await r.lrange(TICKS_KEY.format(symbol=symbol), 0, limit - 1)
    return [json.loads(v) for v in reversed(raw)]  # 오래된 것 → 최신 순
