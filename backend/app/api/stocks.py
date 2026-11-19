"""종목 검색·분류·공공데이터 최근 종가·일봉 API (가상계좌 연습 화면용)"""

import asyncio
from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.history.public_data import PublicDataError, PublicStockClient
from app.stocks.service import MARKET_LABEL, QuoteUnavailable, StockNotFound, StockService

router = APIRouter(prefix="/stocks", tags=["stocks"])


def get_stocks(request: Request) -> StockService:
    return request.app.state.stocks


StocksDep = Annotated[StockService, Depends(get_stocks)]
Market = Literal["KOSPI", "KOSDAQ"]


async def public_quotes(public: PublicStockClient, items: list[dict]) -> list[dict]:
    """기존 종목 정보에 공공데이터 최근 실제 종가를 덮어쓴다."""
    if not public.enabled or not items:
        return items
    results = await asyncio.gather(
        *(public.latest(item["symbol"]) for item in items),
        return_exceptions=True,
    )
    for item, quote in zip(items, results, strict=True):
        if isinstance(quote, dict):
            item.update(quote)
    return items


@router.get("/status")
async def status(request: Request, svc: StocksDep):
    """가상계좌 연습의 가격 출처와 종목 목록 상태"""
    await svc.master()
    result = svc.status()
    if request.app.state.kis_minutes.enabled:
        result["source"] = "kis_replay"
        result["replay_interval_sec"] = request.app.state.kis_minutes.interval
    elif request.app.state.public_stocks.enabled:
        result["source"] = "public_data"
    return result


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
async def search(request: Request, svc: StocksDep, q: Annotated[str, Query(min_length=1, max_length=30)]):
    """종목명 또는 종목코드로 검색 (최대 20개)"""
    return await public_quotes(request.app.state.public_stocks, await svc.search(q))


@router.get("/browse")
async def browse(
    request: Request,
    svc: StocksDep,
    market: Market = "KOSPI",
    sector: str | None = None,
    sort: Literal["cap", "change", "fall", "volume"] = "cap",
    limit: Annotated[int, Query(ge=1, le=40)] = 30,
):
    """시장·업종별 시가총액 상위 종목 + 현재가 (sort: 시가총액·상승률·하락률·거래량)"""
    return await public_quotes(request.app.state.public_stocks, await svc.browse(market, sector or None, sort, limit))


@router.get("/{code}")
async def detail(code: str, request: Request, svc: StocksDep):
    try:
        info = await svc.info(code)
    except StockNotFound as e:
        raise HTTPException(404, "없는 종목이에요") from e
    try:
        q = await request.app.state.kis_minutes.replay_quote(code) or {}
    except Exception:  # 분봉 장애 시 기존 시세·공공데이터로 안전하게 대체
        q = {}
    if not q:
        q = (await svc.quotes([code])).get(code, {})
    result = {
        **q,
        "symbol": code,
        "name": info["name"],
        "market": info["market"],
        "sector": info["sector"],
        "warning": info["warning"],
    }
    if q.get("source") == "kis_replay":
        return result
    return (await public_quotes(request.app.state.public_stocks, [result]))[0]


@router.get("/{code}/daily")
async def daily(
    code: str,
    request: Request,
    svc: StocksDep,
    limit: Annotated[int, Query(ge=5, le=250)] = 120,
):
    """공공데이터 실제 일봉. 실패하거나 키가 없으면 기존 키움 일봉으로 대체한다."""
    try:
        await svc.info(code)
        if request.app.state.public_stocks.enabled:
            end = date.today()
            bars = await request.app.state.public_stocks.daily(
                code, end - timedelta(days=max(30, limit * 2)), end
            )
            if bars:
                return [{**bar, "source": "public_data"} for bar in bars[-limit:]]
        return await svc.daily(code, limit)
    except (PublicDataError, QuoteUnavailable) as e:
        raise HTTPException(503, f"일봉을 받지 못했어요: {e}") from e
    except StockNotFound as e:
        raise HTTPException(404, "없는 종목이에요") from e
