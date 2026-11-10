"""타임머신 트레이딩 API (과거 시세, 자동 백테스트, 직접 매매 세션)"""

import json
from datetime import date
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.backtest.engine import run_backtest
from app.backtest.presets import PRESETS
from app.core.config import settings
from app.db import get_session
from app.history.service import load_bars, symbols_summary
from app.market.sources import DEFAULT_SYMBOLS
from app.strategy.indicators import chart_series, clean
from app.strategy.schemas import Condition
from app.timemachine import session as tm

router = APIRouter(tags=["time-machine"])
SessionDep = Annotated[Session, Depends(get_session)]
TTL = 24 * 3600


def _bars_or_404(s: Session, symbol: str) -> list[dict]:
    bars = load_bars(s, symbol)
    if not bars:
        raise HTTPException(404, "해당 종목의 과거 시세가 없습니다")
    return bars


def _name(symbol: str) -> str:
    return DEFAULT_SYMBOLS.get(symbol, (symbol,))[0]


# ---------- 과거 시세 (#9) ----------
@router.get("/history/symbols")
def history_symbols(s: SessionDep):
    """과거 시세가 있는 종목과 기간"""
    return symbols_summary(s)


@router.get("/history/{symbol}")
def history(symbol: str, s: SessionDep, start: date | None = None, end: date | None = None):
    return load_bars(s, symbol, start, end)


# ---------- 자동 백테스트 (#21) ----------
class BacktestIn(BaseModel):
    symbol: str
    start: date
    end: date | None = None
    buy_conditions: list[Condition] = Field(min_length=1, max_length=10)
    sell_conditions: list[Condition] = Field(default_factory=list, max_length=10)
    initial_cash: float = Field(default=10_000_000, gt=0)
    position_pct: float = Field(default=100, gt=0, le=100)
    fee_pct: float = Field(default=0.015, ge=0, le=5)
    take_profit_pct: float | None = Field(default=None, gt=0)
    stop_loss_pct: float | None = Field(default=None, gt=0)


@router.get("/backtest/presets")
def backtest_presets():
    return PRESETS


@router.post("/backtest")
def backtest(body: BacktestIn, s: SessionDep):
    bars = _bars_or_404(s, body.symbol)
    if body.end:
        bars = [b for b in bars if b["date"] <= body.end.isoformat()]
    start_index = next((i for i, b in enumerate(bars) if b["date"] >= body.start.isoformat()), None)
    if start_index is None or len(bars) - start_index < 5:
        raise HTTPException(422, "백테스트 기간이 너무 짧습니다 (최소 5거래일)")
    if not body.sell_conditions and body.take_profit_pct is None and body.stop_loss_pct is None:
        raise HTTPException(422, "매도 조건 또는 익절·손절 중 하나는 필요합니다")

    dump = body.model_dump(mode="json")
    result = run_backtest(
        bars,
        dump["buy_conditions"],
        dump["sell_conditions"],
        start_index=start_index,
        initial_cash=body.initial_cash,
        position_pct=body.position_pct,
        fee_pct=body.fee_pct,
        take_profit_pct=body.take_profit_pct,
        stop_loss_pct=body.stop_loss_pct,
    )
    series = chart_series([b["close"] for b in bars])
    result["chart"] = [
        {"date": b["date"], "close": b["close"], **{k: clean(v[i]) for k, v in series.items()}}
        for i, b in enumerate(bars)
        if i >= start_index
    ]
    result.update(symbol=body.symbol, name=_name(body.symbol), source=bars[-1]["source"])
    return result


# ---------- 직접 매매 세션 (#20 재생, #22 직접 매매) ----------
async def _load(request: Request, sid: str) -> dict:
    raw = await request.app.state.redis.get(f"tm:{sid}")
    if not raw:
        raise HTTPException(404, "세션이 없거나 만료되었습니다")
    return json.loads(raw)


async def _save(request: Request, st: dict) -> None:
    await request.app.state.redis.set(f"tm:{st['id']}", json.dumps(st, ensure_ascii=False), ex=TTL)


async def _anomaly_marks(chart: list[dict]) -> list[dict]:
    """ai 컨테이너(/detect)로 화면 구간의 이상거래 날짜 표시. 실패하면 빈 목록."""
    body = {
        "bars": [{"timestamp": c["date"], "price": c["close"], "volume": c["volume"]} for c in chart],
        "price_change_pct": 5.0,
        "volume_ratio": 3.0,
    }
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.post(f"{settings.ai_service_url}/detect", json=body)
            r.raise_for_status()
            return r.json()["anomalies"]
    except (httpx.HTTPError, KeyError, ValueError):
        return []


async def _view(st: dict, bars: list[dict]) -> dict:
    v = tm.view(st, bars)
    v["anomalies"] = await _anomaly_marks(v["chart"])
    return v


class SessionIn(BaseModel):
    symbol: str
    start_date: date
    initial_cash: float = Field(default=10_000_000, gt=0)


class StepIn(BaseModel):
    days: int = Field(default=1, ge=1, le=60)


class OrderIn(BaseModel):
    side: Literal["buy", "sell"]
    quantity: int = Field(ge=1)


@router.post("/timemachine/sessions", status_code=201)
async def create_session(body: SessionIn, request: Request, s: SessionDep):
    bars = _bars_or_404(s, body.symbol)
    try:
        st = tm.create(bars, body.symbol, _name(body.symbol), body.start_date.isoformat(), body.initial_cash)
    except tm.SessionError as e:
        raise HTTPException(422, str(e)) from e
    await _save(request, st)
    return await _view(st, bars)


@router.get("/timemachine/sessions/{sid}")
async def get_session_view(sid: str, request: Request, s: SessionDep):
    st = await _load(request, sid)
    return await _view(st, _bars_or_404(s, st["symbol"]))


@router.post("/timemachine/sessions/{sid}/step")
async def step_session(sid: str, body: StepIn, request: Request, s: SessionDep):
    st = await _load(request, sid)
    bars = _bars_or_404(s, st["symbol"])
    try:
        tm.step(st, bars, body.days)
    except tm.SessionError as e:
        raise HTTPException(409, str(e)) from e
    await _save(request, st)
    return await _view(st, bars)


@router.post("/timemachine/sessions/{sid}/order")
async def order_session(sid: str, body: OrderIn, request: Request, s: SessionDep):
    st = await _load(request, sid)
    bars = _bars_or_404(s, st["symbol"])
    try:
        tm.order(st, bars, body.side, body.quantity)
    except tm.SessionError as e:
        raise HTTPException(422, str(e)) from e
    await _save(request, st)
    return await _view(st, bars)


@router.post("/timemachine/sessions/{sid}/finish")
async def finish_session(sid: str, request: Request, s: SessionDep):
    st = await _load(request, sid)
    bars = _bars_or_404(s, st["symbol"])
    result = tm.finish(st, bars)
    await _save(request, st)
    return result
