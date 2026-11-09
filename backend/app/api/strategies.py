import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.market.cache import get_ticks
from app.strategy.engine import ALERTS_KEY
from app.strategy.indicators import snapshot
from app.strategy.models import Order, Strategy
from app.strategy.schemas import OrderOut, StrategyIn, StrategyOut

router = APIRouter(tags=["auto-trading"])
SessionDep = Annotated[Session, Depends(get_session)]


# ---------- 전략 CRUD ----------
@router.post("/strategies", response_model=StrategyOut, status_code=201)
def create_strategy(body: StrategyIn, s: SessionDep):
    st = Strategy(**body.model_dump(mode="json"))
    s.add(st)
    s.commit()
    s.refresh(st)
    return st


@router.get("/strategies", response_model=list[StrategyOut])
def list_strategies(s: SessionDep):
    return s.scalars(select(Strategy).order_by(Strategy.id)).all()


def _get_or_404(s: Session, strategy_id: int) -> Strategy:
    st = s.get(Strategy, strategy_id)
    if not st:
        raise HTTPException(404, "전략을 찾을 수 없습니다")
    return st


@router.get("/strategies/{strategy_id}", response_model=StrategyOut)
def get_strategy(strategy_id: int, s: SessionDep):
    return _get_or_404(s, strategy_id)


@router.put("/strategies/{strategy_id}", response_model=StrategyOut)
def update_strategy(strategy_id: int, body: StrategyIn, s: SessionDep):
    st = _get_or_404(s, strategy_id)
    for k, v in body.model_dump(mode="json").items():
        setattr(st, k, v)
    s.commit()
    s.refresh(st)
    return st


@router.delete("/strategies/{strategy_id}", status_code=204)
def delete_strategy(strategy_id: int, s: SessionDep):
    s.delete(_get_or_404(s, strategy_id))
    s.commit()


# ---------- 주문·알림·지표 조회 ----------
@router.get("/orders", response_model=list[OrderOut])
def list_orders(s: SessionDep, limit: int = 50):
    return s.scalars(select(Order).order_by(Order.id.desc()).limit(min(limit, 500))).all()


@router.get("/alerts")
async def list_alerts(request: Request, limit: int = 20):
    raw = await request.app.state.redis.lrange(ALERTS_KEY, 0, min(limit, 100) - 1)
    return [json.loads(a) for a in raw]


@router.get("/indicators/{symbol}")
async def indicators(symbol: str, request: Request):
    """종목의 주요 보조지표 최신값 (SMA5·SMA20·RSI14·볼린저밴드)"""
    closes = [t["price"] for t in await get_ticks(request.app.state.redis, symbol, limit=300)]
    return {"symbol": symbol, "count": len(closes), **snapshot(closes)}
