import re

from fastapi import APIRouter, HTTPException, Request

from app.kiwoom.watch import touch
from app.market.cache import get_latest, get_ticks
from app.stocks.service import StockNotFound
from app.strategy.indicators import chart_series, clean

router = APIRouter(prefix="/market", tags=["market"])
CODE_RE = re.compile(r"^[0-9A-Z]{6}$")


def _check_code(symbol: str) -> str:
    if not CODE_RE.match(symbol):
        raise HTTPException(422, "종목코드는 6자리입니다 (예: 005930)")
    return symbol


@router.post("/watch/{symbol}")
async def watch(symbol: str, request: Request):
    """이 종목을 보고 있다고 알림 → 실시간 구독 대상에 포함 (화면에서 60초마다 호출)"""
    await touch(request.app.state.redis, _check_code(symbol))
    return {"symbol": symbol, "watching": True}


async def get_quote(app_state, symbol: str) -> dict | None:
    """현재가 (StockService: 키움 ka10095 5초 캐시, 키가 없으면 가상 시세). 없으면 None"""
    # 테스트·이전 코드가 키움 StockService를 stocks에 직접 넣은 경우도 호환한다.
    service = app_state.stocks if app_state.stocks.kiwoom else app_state.real_stocks
    return (await service.quotes([symbol])).get(symbol)


@router.get("/quote/{symbol}")
async def quote(symbol: str, request: Request):
    """종목 현재가 (실거래 화면에서 종목을 열 때). 조회하면서 실시간 구독 대상에도 넣는다

    종목 검색은 /stocks/search (가상계좌 연습과 같은 전 종목 목록)
    """
    _check_code(symbol)
    try:
        await request.app.state.stocks.info(symbol)
    except StockNotFound as e:
        raise HTTPException(404, "없는 종목이에요") from e
    await touch(request.app.state.redis, symbol)
    q = await get_quote(request.app.state, symbol)
    if not q or not q.get("price"):
        raise HTTPException(404, "시세가 없습니다")
    return q


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
