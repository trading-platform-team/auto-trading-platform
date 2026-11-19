"""교육 페이지 API (학습 진도, 교육용 가상계좌, 관심종목)"""

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.stocks import StocksDep
from app.api.strategies import SessionDep
from app.auth.deps import CurrentUser
from app.edu import account, orderbook, progress
from app.edu.curriculum import UNITS
from app.history.kis_minutes import KisMinuteError
from app.history.public_data import PublicDataError, PublicStockClient
from app.stocks.service import StockNotFound, StockService

router = APIRouter(prefix="/edu", tags=["education"])
log = logging.getLogger(__name__)


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


def _real(quotes: dict[str, dict]) -> dict[str, dict]:
    """가상(mock) 시세를 뺀 실제 시세만"""
    return {c: q for c, q in quotes.items() if q.get("price") and q.get("source") not in (None, "mock")}


async def _prices(request: Request, public: PublicStockClient, svc: StockService, s, user_id: int) -> dict[str, dict]:
    """보유·거래 종목의 현재가와 이름 (snapshot용)"""
    codes = account.symbols(s, user_id)
    s.rollback()  # 키움 응답을 기다리는 동안 DB 연결을 붙잡지 않도록 반납 (읽기만 했음)
    if not codes:
        return {}
    replay = await asyncio.gather(
        *(request.app.state.kis_minutes.replay_quote(code) for code in codes), return_exceptions=True
    )
    prices = {code: quote for code, quote in zip(codes, replay, strict=True) if isinstance(quote, dict)}
    missing = [code for code in codes if code not in prices]
    prices.update(_real(await svc.quotes(missing)))  # 종목 목록에 받아 둔 최근 종가 (호출 없음)
    missing = [code for code in codes if code not in prices]
    prices.update(await _public_quotes(public, missing))
    missing = [code for code in codes if code not in prices]
    prices.update(await svc.quotes(missing))  # 마지막으로 가상 시세
    master = await svc.master()
    for c in codes:  # 한국투자 재생 시세에는 이름이 없고, 시세를 못 받은 종목도 이름은 표시
        if c in master:
            prices.setdefault(c, {}).setdefault("name", master[c]["name"])
    return prices


@router.get("/account")
async def get_account(request: Request, svc: StocksDep, s: SessionDep, user: CurrentUser):
    pending = sorted({o.symbol for o in account.open_orders(s, user["id"])})
    await match_symbols(request.app.state, svc, s, pending, user["id"])
    return account.snapshot(s, user["id"], await _prices(request, request.app.state.public_stocks, svc, s, user["id"]))


async def _quote(state, svc: StockService, symbol: str) -> dict | None:
    """주문·호가용 현재 시세: 한국투자 분봉 재생 → 종목 목록의 최근 종가 → 공공데이터 종가 조회"""
    try:
        quote = await state.kis_minutes.replay_quote(symbol)
        if quote:
            return quote
    except KisMinuteError:
        pass
    quotes = await svc.quotes([symbol])
    quote = _real(quotes).get(symbol)  # 종목 목록의 최근 종가 (공공데이터 호출 없이)
    if quote:
        return quote
    try:
        quote = await state.public_stocks.latest(symbol)
        if quote:
            return quote
    except PublicDataError:
        pass
    quote = quotes.get(symbol)  # 마지막으로 가상 시세
    return quote if quote and quote.get("price") else None


async def _tick(state, symbol: str) -> int | None:
    """그 종목 실제 분봉 가격으로 정한 호가 단위 (분봉이 없으면 None → 표 사용)"""
    if not state.kis_minutes.enabled:
        return None
    try:
        rows = await state.kis_minutes.minutes(symbol)
    except KisMinuteError:
        return None
    return orderbook.observed_tick([r["price"] for r in rows])


async def _known(svc: StockService, symbol: str) -> None:
    try:
        await svc.info(symbol)
    except StockNotFound as e:
        if svc.status()["loading"]:
            raise HTTPException(503, "종목 목록을 불러오는 중이에요. 잠시 후 다시 시도해 주세요") from e
        raise HTTPException(404, "없는 종목이에요") from e


async def match_symbols(state, svc: StockService, s, symbols: list[str], user_id: int | None = None):
    """미체결 지정가 주문을 지금 재생 분봉과 맞춰 체결"""
    if not symbols:
        return []
    s.rollback()  # 시세를 기다리는 동안 DB 연결을 붙잡지 않도록
    quotes = await asyncio.gather(*(_quote(state, svc, c) for c in symbols), return_exceptions=True)
    ready = {c: q for c, q in zip(symbols, quotes, strict=True) if isinstance(q, dict)}
    return account.match_open_orders(s, ready, user_id) if ready else []


class EduOrderIn(BaseModel):
    symbol: str = Field(min_length=6, max_length=6)
    side: Literal["buy", "sell"]
    quantity: int = Field(ge=1, le=1_000_000)
    order_type: Literal["market", "limit"] = "market"
    price: float | None = Field(default=None, gt=0)  # 지정가일 때 주문 가격


@router.post("/account/orders")
async def order(body: EduOrderIn, request: Request, svc: StocksDep, s: SessionDep, user: CurrentUser):
    """교육용 주문. 시장가는 지금 재생 가격으로 바로, 지정가는 닿을 때까지 미체결로 걸어 둔다."""
    await _known(svc, body.symbol)
    if body.order_type == "limit" and body.price is None:
        raise HTTPException(422, "지정가 주문은 가격을 입력해 주세요")
    s.rollback()
    quote = await _quote(request.app.state, svc, body.symbol)
    price = quote["price"] if quote else 0  # 0이면 place_order가 '현재가를 알 수 없어요'로 거부
    before = set(progress.badges(s, user["id"]))
    open_order = None
    try:
        if body.order_type == "limit":
            tick = await _tick(request.app.state, body.symbol)
            trade, open_order = account.place_limit_order(
                s, user["id"], body.symbol, body.side, body.quantity, body.price, price, tick
            )
        else:
            trade = account.place_order(s, user["id"], body.symbol, body.side, body.quantity, price)
    except account.OrderRejected as e:
        raise HTTPException(422, str(e)) from e
    snap = account.snapshot(
        s, user["id"], await _prices(request, request.app.state.public_stocks, svc, s, user["id"])
    )
    new_badges = [b for b in progress.badges(s, user["id"]) if b not in before]
    return {
        "status": "open" if open_order else "filled",
        "trade_id": trade.id if trade else None,
        "open_order_id": open_order.id if open_order else None,
        "price": trade.price if trade else open_order.price,
        "price_source": quote.get("source") if quote else "fallback",
        "price_date": quote.get("price_date") if quote else None,
        "realized_pnl": trade.realized_pnl if trade else None,
        "account": snap,
        "badges": new_badges,
    }


@router.delete("/account/orders/{order_id}")
async def cancel(order_id: int, request: Request, svc: StocksDep, s: SessionDep, user: CurrentUser):
    try:
        account.cancel_order(s, user["id"], order_id)
    except account.OrderRejected as e:
        raise HTTPException(404, str(e)) from e
    return account.snapshot(
        s, user["id"], await _prices(request, request.app.state.public_stocks, svc, s, user["id"])
    )


@router.get("/orderbook/{code}")
async def get_orderbook(code: str, request: Request, svc: StocksDep):
    """연습용 호가창 (재생 가격 기준, 실제 과거 호가 아님)"""
    await _known(svc, code)
    quote = await _quote(request.app.state, svc, code)
    if not quote:
        raise HTTPException(503, "현재가를 알 수 없어 호가를 만들지 못했어요")
    return orderbook.build(code, quote, await _tick(request.app.state, code))


async def match_forever(state, interval: float) -> None:
    """모든 사용자의 미체결 지정가 주문을 재생 분봉이 넘어갈 때마다 확인 (화면을 닫아도 체결되게)"""
    from app import db

    while True:
        await asyncio.sleep(interval)
        try:
            with db.new_session() as s:
                symbols = account.open_order_symbols(s)
                filled = await match_symbols(state, state.stocks, s, symbols)
            if filled:
                log.info("지정가 미체결 %d건 체결", len(filled))
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - 다음 주기에 다시 시도
            log.exception("지정가 체결 확인 실패")


@router.post("/account/reset")
async def reset(request: Request, svc: StocksDep, s: SessionDep, user: CurrentUser):
    account.reset(s, user["id"])
    return account.snapshot(
        s, user["id"], await _prices(request, request.app.state.public_stocks, svc, s, user["id"])
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
