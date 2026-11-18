"""교육 페이지 API (학습 진도, 교육용 가상계좌, 관심종목)"""

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.stocks import StocksDep
from app.api.strategies import SessionDep
from app.auth.deps import CurrentUser
from app.edu import account, progress
from app.edu.curriculum import UNITS
from app.history.public_data import PublicDataError, PublicStockClient
from app.stocks.service import QuoteUnavailable, StockNotFound, StockService

router = APIRouter(prefix="/edu", tags=["education"])


# ---------- 학습 진도 ----------
@router.get("/curriculum")
def curriculum():
    return UNITS


@router.get("/progress")
def get_progress(s: SessionDep, user: CurrentUser):
    return progress.summary(s, user["id"])


class LessonResultIn(BaseModel):
    correct: int = Field(ge=0)
    total: int = Field(ge=1, le=50)


@router.post("/lessons/{lesson_id}/complete")
def complete(lesson_id: str, body: LessonResultIn, s: SessionDep, user: CurrentUser):
    if body.correct > body.total:
        raise HTTPException(422, "correct는 total보다 클 수 없습니다")
    try:
        return progress.complete_lesson(s, user["id"], lesson_id, body.correct, body.total)
    except KeyError as e:
        raise HTTPException(404, "없거나 아직 준비 중인 레슨입니다") from e
    except progress.LessonLocked as e:
        raise HTTPException(409, "이전 레슨을 먼저 완료해 주세요") from e


# ---------- 교육용 가상계좌 ----------
async def _public_quotes(public: PublicStockClient, codes: list[str]) -> dict[str, dict]:
    if not public.enabled:
        return {}
    results = await asyncio.gather(*(public.latest(code) for code in codes), return_exceptions=True)
    return {
        code: quote
        for code, quote in zip(codes, results, strict=True)
        if isinstance(quote, dict) and quote.get("price")
    }


async def _prices(public: PublicStockClient, svc: StockService, s, user_id: int) -> dict[str, dict]:
    """보유·거래 종목의 현재가와 이름 (snapshot용)"""
    codes = account.symbols(s, user_id)
    s.rollback()  # 키움 응답을 기다리는 동안 DB 연결을 붙잡지 않도록 반납 (읽기만 했음)
    if not codes:
        return {}
    prices = await _public_quotes(public, codes)
    missing = [code for code in codes if code not in prices]
    prices.update(await svc.quotes(missing))
    master = await svc.master()
    for c in codes:  # 시세를 못 받은 종목도 이름은 표시
        if c not in prices and c in master:
            prices[c] = {"name": master[c]["name"]}
    return prices


@router.get("/account")
async def get_account(request: Request, svc: StocksDep, s: SessionDep, user: CurrentUser):
    return account.snapshot(s, user["id"], await _prices(request.app.state.public_stocks, svc, s, user["id"]))


class EduOrderIn(BaseModel):
    symbol: str = Field(min_length=6, max_length=6)
    side: Literal["buy", "sell"]
    quantity: int = Field(ge=1, le=1_000_000)


@router.post("/account/orders")
async def order(body: EduOrderIn, request: Request, svc: StocksDep, s: SessionDep, user: CurrentUser):
    """금융위원회 최근 실제 종가(실패 시 기존 시세)로 교육용 시장가 주문"""
    quote = None
    try:
        await svc.info(body.symbol)
    except StockNotFound as e:
        if svc.status()["loading"]:
            raise HTTPException(503, "키움 종목 목록을 불러오는 중이에요. 잠시 후 다시 시도해 주세요") from e
        raise HTTPException(404, "없는 종목이에요") from e
    try:
        quote = await request.app.state.public_stocks.latest(body.symbol)
    except PublicDataError:
        pass
    try:
        price = quote["price"] if quote else await svc.price(body.symbol)
    except QuoteUnavailable:
        price = 0  # place_order가 '현재가를 알 수 없어요'로 거부
    before = set(progress.badges(s, user["id"]))
    try:
        trade = account.place_order(s, user["id"], body.symbol, body.side, body.quantity, price)
    except account.OrderRejected as e:
        raise HTTPException(422, str(e)) from e
    snap = account.snapshot(
        s, user["id"], await _prices(request.app.state.public_stocks, svc, s, user["id"])
    )
    new_badges = [b for b in progress.badges(s, user["id"]) if b not in before]
    return {
        "trade_id": trade.id,
        "price": price,
        "price_source": quote.get("source") if quote else "fallback",
        "price_date": quote.get("price_date") if quote else None,
        "realized_pnl": trade.realized_pnl,
        "account": snap,
        "badges": new_badges,
    }


@router.post("/account/reset")
async def reset(request: Request, svc: StocksDep, s: SessionDep, user: CurrentUser):
    account.reset(s, user["id"])
    return account.snapshot(
        s, user["id"], await _prices(request.app.state.public_stocks, svc, s, user["id"])
    )


# ---------- 관심종목 ----------
async def _watch_items(svc: StockService, codes: list[str]) -> list[dict]:
    master = await svc.master()
    return await svc.with_quotes([master[c] for c in codes if c in master])


@router.get("/watchlist")
async def get_watchlist(svc: StocksDep, s: SessionDep, user: CurrentUser):
    codes = account.watchlist(s, user["id"])
    s.rollback()  # DB 연결 반납 후 시세 조회
    return await _watch_items(svc, codes)


@router.put("/watchlist/{code}")
async def add_watch(code: str, svc: StocksDep, s: SessionDep, user: CurrentUser):
    try:
        await svc.info(code)
        codes = account.add_watch(s, user["id"], code)
        s.rollback()
    except StockNotFound as e:
        raise HTTPException(404, "없는 종목이에요") from e
    except account.OrderRejected as e:
        raise HTTPException(422, str(e)) from e
    return await _watch_items(svc, codes)


@router.delete("/watchlist/{code}")
async def remove_watch(code: str, svc: StocksDep, s: SessionDep, user: CurrentUser):
    codes = account.remove_watch(s, user["id"], code)
    s.rollback()
    return await _watch_items(svc, codes)
