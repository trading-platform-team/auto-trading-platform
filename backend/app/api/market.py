from fastapi import APIRouter, Request

from app.market.cache import get_latest, get_ticks
from app.strategy.indicators import chart_series, clean

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/prices")
async def prices(request: Request):
    """전 종목 최신 시세"""
    return await get_latest(request.app.state.redis)


@router.get("/ticks/{symbol}")
async def ticks(symbol: str, request: Request, limit: int = 50):
    """종목별 최근 시세"""
    return await get_ticks(request.app.state.redis, symbol, min(limit, 300))


@router.get("/chart/{symbol}")
async def chart(symbol: str, request: Request, limit: int = 120):
    """차트용 시세 + 보조지표 시계열 (가격, SMA5, SMA20, 볼린저밴드, RSI)

    지표는 최근 300개로 계산한 뒤 마지막 limit개만 돌려준다 (앞부분 NaN 최소화).
    """
    rows = await get_ticks(request.app.state.redis, symbol, 300)
    if not rows:
        return []
    closes = [t["price"] for t in rows]
    series = chart_series(closes)
    start = max(0, len(rows) - min(limit, 300))
    return [
        {"timestamp": t["timestamp"], "price": t["price"], "volume": t["volume"],
         **{k: clean(v[i]) for k, v in series.items()}}
        for i, t in enumerate(rows) if i >= start
    ]
