"""교육 페이지 API (학습 진도, 교육용 가상계좌)"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.strategies import SessionDep
from app.auth.deps import CurrentUser
from app.edu import account, progress
from app.edu.curriculum import UNITS
from app.market.cache import get_latest

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
async def _prices(request: Request) -> dict[str, dict]:
    return {p["symbol"]: p for p in await get_latest(request.app.state.redis)}


@router.get("/account")
async def get_account(request: Request, s: SessionDep, user: CurrentUser):
    return account.snapshot(s, user["id"], await _prices(request))


class EduOrderIn(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int = Field(ge=1, le=1_000_000)


@router.post("/account/orders")
async def order(body: EduOrderIn, request: Request, s: SessionDep, user: CurrentUser):
    """현재 모의 시세로 시장가 주문"""
    prices = await _prices(request)
    price = prices.get(body.symbol, {}).get("price", 0)
    before = set(progress.badges(s, user["id"]))
    try:
        trade = account.place_order(s, user["id"], body.symbol, body.side, body.quantity, price)
    except account.OrderRejected as e:
        raise HTTPException(422, str(e)) from e
    snap = account.snapshot(s, user["id"], prices)
    new_badges = [b for b in progress.badges(s, user["id"]) if b not in before]
    return {
        "trade_id": trade.id,
        "price": price,
        "realized_pnl": trade.realized_pnl,
        "account": snap,
        "badges": new_badges,
    }


@router.post("/account/reset")
async def reset(request: Request, s: SessionDep, user: CurrentUser):
    account.reset(s, user["id"])
    return account.snapshot(s, user["id"], await _prices(request))
