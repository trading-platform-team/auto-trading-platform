from fastapi import APIRouter, Request

from app.market.cache import get_latest, get_ticks

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/prices")
async def prices(request: Request):
    """전 종목 최신 시세"""
    return await get_latest(request.app.state.redis)


@router.get("/ticks/{symbol}")
async def ticks(symbol: str, request: Request, limit: int = 50):
    """종목별 최근 시세 (차트용)"""
    return await get_ticks(request.app.state.redis, symbol, min(limit, 300))
