import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, OptionalUser
from app.db import get_session
from app.market.cache import get_ticks
from app.strategy.engine import ALERTS_KEY
from app.strategy.indicators import snapshot
from app.strategy.models import Order, Strategy
from app.strategy.schemas import OrderOut, StrategyIn, StrategyOut

router = APIRouter(tags=["auto-trading"])
SessionDep = Annotated[Session, Depends(get_session)]


def visible_to(alert: dict, user: dict | None) -> bool:
    """주문 알림은 전략 주인만, 나머지(이상거래)는 모두에게"""
    if alert.get("type") != "order":
        return True
    return user is not None and alert.get("user_id") == user["id"]


# ---------- 전략 CRUD ----------
@router.post("/strategies", response_model=StrategyOut, status_code=201)
def create_strategy(body: StrategyIn, s: SessionDep, user: CurrentUser):
    st = Strategy(**body.model_dump(mode="json"), user_id=user["id"])
    s.add(st)
    s.commit()
    s.refresh(st)
    return st


@router.get("/strategies", response_model=list[StrategyOut])
def list_strategies(s: SessionDep, user: CurrentUser):
    return s.scalars(select(Strategy).where(Strategy.user_id == user["id"]).order_by(Strategy.id)).all()


def _get_or_404(s: Session, strategy_id: int, user: dict) -> Strategy:
    st = s.get(Strategy, strategy_id)
    if not st or st.user_id != user["id"]:  # 남의 전략은 없는 것처럼
        raise HTTPException(404, "전략을 찾을 수 없습니다")
    return st


@router.get("/strategies/{strategy_id}", response_model=StrategyOut)
def get_strategy(strategy_id: int, s: SessionDep, user: CurrentUser):
    return _get_or_404(s, strategy_id, user)


@router.put("/strategies/{strategy_id}", response_model=StrategyOut)
def update_strategy(strategy_id: int, body: StrategyIn, s: SessionDep, user: CurrentUser):
    st = _get_or_404(s, strategy_id, user)
    for k, v in body.model_dump(mode="json").items():
        setattr(st, k, v)
    s.commit()
    s.refresh(st)
    return st


@router.delete("/strategies/{strategy_id}", status_code=204)
def delete_strategy(strategy_id: int, s: SessionDep, user: CurrentUser):
    s.delete(_get_or_404(s, strategy_id, user))
    s.commit()


# ---------- 주문·알림·지표 조회 ----------
@router.get("/orders", response_model=list[OrderOut])
def list_orders(s: SessionDep, user: CurrentUser, limit: int = 50):
    q = select(Order).where(Order.user_id == user["id"]).order_by(Order.id.desc()).limit(min(limit, 500))
    return s.scalars(q).all()


@router.get("/alerts")
async def list_alerts(request: Request, user: OptionalUser, limit: int = 20):
    """최근 알림: 이상거래(공개) + 내 주문 알림"""
    raw = await request.app.state.redis.lrange(ALERTS_KEY, 0, 99)
    items = [a for a in map(json.loads, raw) if visible_to(a, user)]
    return items[: min(limit, 100)]


@router.get("/anomalies")
async def list_anomalies(request: Request, limit: int = 20, symbol: str | None = None):
    """AI 서비스가 탐지한 이상거래 경보 (최신순)"""
    raw = await request.app.state.redis.lrange("anomalies", 0, 199)
    items = [json.loads(a) for a in raw]
    if symbol:
        items = [a for a in items if a["symbol"] == symbol]
    return items[: min(limit, 200)]


@router.get("/indicators/{symbol}")
async def indicators(symbol: str, request: Request):
    """종목의 주요 보조지표 최신값 (SMA5·SMA20·RSI14·볼린저밴드)"""
    closes = [t["price"] for t in await get_ticks(request.app.state.redis, symbol, limit=300)]
    return {"symbol": symbol, "count": len(closes), **snapshot(closes)}
