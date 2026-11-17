"""종목 검색·분류·현재가·일봉 API (가상계좌 연습 화면용, 로그인 없이 조회 가능)"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.stocks.service import MARKET_LABEL, QuoteUnavailable, StockNotFound, StockService

router = APIRouter(prefix="/stocks", tags=["stocks"])


def get_stocks(request: Request) -> StockService:
    return request.app.state.stocks


StocksDep = Annotated[StockService, Depends(get_stocks)]
Market = Literal["KOSPI", "KOSDAQ"]


@router.get("/status")
async def status(svc: StocksDep):
    """시세 출처(kiwoom | mock), 종목 수, 장 운영 여부, 최근 오류"""
    await svc.master()
    return svc.status()


@router.get("/markets")
async def markets(svc: StocksDep):
    master = await svc.master()
    return [
        {"market": m, "label": label, "count": sum(1 for r in master.values() if r["market"] == m)}
        for m, label in MARKET_LABEL.items()
    ]


@router.get("/sectors")
async def sectors(svc: StocksDep, market: Market = "KOSPI"):
    return await svc.sectors(market)


@router.get("/search")
async def search(svc: StocksDep, q: Annotated[str, Query(min_length=1, max_length=30)]):
    """종목명 또는 종목코드로 검색 (최대 20개)"""
    return await svc.search(q)


@router.get("/browse")
async def browse(
    svc: StocksDep,
    market: Market = "KOSPI",
    sector: str | None = None,
    sort: Literal["cap", "change", "fall", "volume"] = "cap",
    limit: Annotated[int, Query(ge=1, le=40)] = 30,
):
    """시장·업종별 시가총액 상위 종목 + 현재가 (sort: 시가총액·상승률·하락률·거래량)"""
    return await svc.browse(market, sector or None, sort, limit)


@router.get("/{code}")
async def detail(code: str, svc: StocksDep):
    try:
        info = await svc.info(code)
    except StockNotFound as e:
        raise HTTPException(404, "없는 종목이에요") from e
    q = (await svc.quotes([code])).get(code, {})
    return {
        **q,
        "symbol": code,
        "name": info["name"],
        "market": info["market"],
        "sector": info["sector"],
        "warning": info["warning"],
    }


@router.get("/{code}/daily")
async def daily(code: str, svc: StocksDep, limit: Annotated[int, Query(ge=5, le=250)] = 120):
    """일봉 (키움 ka10081). 키움 키가 없으면 빈 목록, 받는 중·실패면 503 + 이유"""
    try:
        return await svc.daily(code, limit)
    except QuoteUnavailable as e:
        raise HTTPException(503, f"일봉을 받지 못했어요: {e}") from e
    except StockNotFound as e:
        raise HTTPException(404, "없는 종목이에요") from e
