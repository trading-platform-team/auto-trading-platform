"""타임머신 트레이딩 API (과거 시세, 자동 백테스트, 직접 매매 세션)"""

import json
from datetime import date
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser
from app.backtest.engine import run_backtest
from app.backtest.presets import PRESETS
from app.core.config import settings
from app.db import get_session
from app.history.events import load_events, merge_events
from app.history.external_events import fetch_disclosure_preview, load_external_events
from app.history.public_data import PublicDataError
from app.history.service import SEED_START, load_bars, symbols_summary, sync_public_bars
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


async def _refresh_history(request: Request, s: Session, symbol: str, start: date, end: date) -> None:
    """공공데이터 키가 있으면 실제 일봉으로 갱신하고, 실패하면 저장된 교육용 데이터로 계속한다."""
    try:
        await sync_public_bars(s, request.app.state.public_stocks, symbol, start, end)
    except (PublicDataError, OSError, ValueError):
        s.rollback()


# ---------- 과거 시세 (#9) ----------
@router.get("/history/symbols")
def history_symbols(s: SessionDep):
    """과거 시세가 있는 종목과 기간"""
    return symbols_summary(s)


async def _events(symbol: str, start: date | None = None, end: date | None = None) -> list[dict]:
    return merge_events(load_events(symbol, start, end), await load_external_events(symbol, start, end))


@router.get("/history/{symbol}/events")
async def history_events(symbol: str, start: date | None = None, end: date | None = None):
    """공식 발표를 바탕으로 정리한 종목·시장 주요 사건"""
    if start and end and start > end:
        raise HTTPException(422, "시작일은 종료일보다 늦을 수 없습니다")
    return await _events(symbol, start, end)


@router.get("/history/events/{rcept_no}/preview")
async def disclosure_preview(rcept_no: str):
    """공시 이미지 미리보기 생성에 사용할 원문 텍스트 일부를 반환한다."""
    if len(rcept_no) != 14 or not rcept_no.isdigit():
        raise HTTPException(422, "올바른 공시 접수번호가 아닙니다")
    try:
        return await fetch_disclosure_preview(rcept_no)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("/history/{symbol}")
async def history(symbol: str, request: Request, s: SessionDep, start: date | None = None, end: date | None = None):
    if start and end and start > end:
        raise HTTPException(422, "시작일은 종료일보다 늦을 수 없습니다")
    await _refresh_history(request, s, symbol, start or SEED_START, end or date.today())
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
async def backtest(body: BacktestIn, request: Request, s: SessionDep):
    await _refresh_history(request, s, body.symbol, SEED_START, body.end or date.today())
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
        {
            "date": b["date"],
            "open": b["open"],
            "high": b["high"],
            "low": b["low"],
            "close": b["close"],
            "volume": b["volume"],
            **{k: clean(v[i]) for k, v in series.items()},
        }
        for i, b in enumerate(bars)
        if i >= start_index
    ]
    result.update(symbol=body.symbol, name=_name(body.symbol), source=bars[-1]["source"])
    return result


# ---------- 직접 매매 세션 (#20 재생, #22 직접 매매) ----------
async def _load(request: Request, sid: str, user: dict) -> dict:
    raw = await request.app.state.redis.get(f"tm:{sid}")
    st = json.loads(raw) if raw else None
    if not st or st.get("user_id") != user["id"]:  # 남의 세션은 없는 것처럼
        raise HTTPException(404, "세션이 없거나 만료되었습니다")
    return st


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
    v["events"] = await _events(
        st["symbol"],
        date.fromisoformat(v["chart"][0]["date"]),
        date.fromisoformat(v["date"]),
    )
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
async def create_session(body: SessionIn, request: Request, s: SessionDep, user: CurrentUser):
    await _refresh_history(request, s, body.symbol, SEED_START, date.today())
    bars = _bars_or_404(s, body.symbol)
    try:
        st = tm.create(bars, body.symbol, _name(body.symbol), body.start_date.isoformat(), body.initial_cash)
    except tm.SessionError as e:
        raise HTTPException(422, str(e)) from e
    st["user_id"] = user["id"]
    await _save(request, st)
    return await _view(st, bars)


@router.get("/timemachine/sessions/{sid}")
async def get_session_view(sid: str, request: Request, s: SessionDep, user: CurrentUser):
    st = await _load(request, sid, user)
    return await _view(st, _bars_or_404(s, st["symbol"]))


@router.post("/timemachine/sessions/{sid}/step")
async def step_session(sid: str, body: StepIn, request: Request, s: SessionDep, user: CurrentUser):
    st = await _load(request, sid, user)
    bars = _bars_or_404(s, st["symbol"])
    try:
        tm.step(st, bars, body.days)
    except tm.SessionError as e:
        raise HTTPException(409, str(e)) from e
    await _save(request, st)
    return await _view(st, bars)


@router.post("/timemachine/sessions/{sid}/order")
async def order_session(sid: str, body: OrderIn, request: Request, s: SessionDep, user: CurrentUser):
    st = await _load(request, sid, user)
    bars = _bars_or_404(s, st["symbol"])
    try:
        tm.order(st, bars, body.side, body.quantity)
    except tm.SessionError as e:
        raise HTTPException(422, str(e)) from e
    await _save(request, st)
    return await _view(st, bars)


@router.post("/timemachine/sessions/{sid}/finish")
async def finish_session(sid: str, request: Request, s: SessionDep, user: CurrentUser):
    st = await _load(request, sid, user)
    bars = _bars_or_404(s, st["symbol"])
    result = tm.finish(st, bars)
    await _save(request, st)
    return result
