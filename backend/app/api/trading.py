"""실거래 API (로그인 필요, 본인 것만)

활성화 흐름
  1. PUT  /trading/kiwoom/settings  서버(mock|real)와 한도 설정 → 바꾸면 자동으로 꺼짐
  2. POST /trading/kiwoom/activate  확인 문구 입력 + 키 연결 확인(잔고 조회) → 켜짐
  3. 전략의 account를 "kiwoom"으로 두면 자동매매 엔진이 이 설정으로 주문
  POST /trading/kiwoom/deactivate   언제든 즉시 끄기 (긴급 정지)
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.market import get_quote
from app.auth.deps import CurrentUser
from app.db import get_session
from app.kiwoom import parse
from app.kiwoom.client import KiwoomError
from app.trading import broker, credentials, risk
from app.trading.models import KiwoomOrder, KiwoomSetting

router = APIRouter(prefix="/trading/kiwoom", tags=["real-trading"])
SessionDep = Annotated[Session, Depends(get_session)]

CONFIRM_TEXT = {"mock": "모의투자를 시작합니다", "real": "실거래를 시작합니다"}
MAX_ORDER_AMOUNT_CAP = 100_000_000
DAILY_LOSS_CAP = 100_000_000


class SettingsIn(BaseModel):
    env: Literal["mock", "real"] = "mock"
    max_order_amount: int = Field(ge=10_000, le=MAX_ORDER_AMOUNT_CAP)
    daily_loss_limit: int = Field(ge=10_000, le=DAILY_LOSS_CAP)


class ActivateIn(BaseModel):
    confirm: str  # 서버별 확인 문구를 그대로 입력


class OrderIn(BaseModel):
    symbol: str = Field(pattern=r"^[0-9A-Z]{6}$")
    side: Literal["buy", "sell"]
    quantity: int = Field(ge=1, le=100_000)
    price: int | None = Field(default=None, ge=1)  # 없으면 시장가


def _keys(user_id: int) -> dict:
    """서버별 등록된 키가 있는지 (실전=주계좌 / 모의투자 계좌). 키 원문은 내보내지 않는다"""
    out = {}
    for env in ("mock", "real"):
        try:
            creds = credentials.get_credentials(user_id, env)
        except ValueError:  # 키의 서버가 요청과 다름
            creds = None
        out[env] = {"registered": creds is not None, "key_id": creds.key_id[:6] if creds else None}
    return out


def _settings_out(st: KiwoomSetting) -> dict:
    return {
        "keys": _keys(st.user_id),
        "env": st.env, "enabled": st.enabled, "max_order_amount": st.max_order_amount,
        "daily_loss_limit": st.daily_loss_limit, "disabled_reason": st.disabled_reason,
        "activated_at": st.activated_at.isoformat() if st.activated_at else None,
        "confirm_text": CONFIRM_TEXT[st.env],
    }


def _get_setting(s: Session, user_id: int) -> KiwoomSetting:
    st = s.get(KiwoomSetting, user_id)
    if st is None:
        st = KiwoomSetting(user_id=user_id, env="mock", enabled=False,
                           max_order_amount=1_000_000, daily_loss_limit=100_000)
        s.add(st)
        s.commit()
        s.refresh(st)
    return st


def _api_for(user_id: int, env: str, r):
    creds = credentials.get_credentials(user_id, env)
    if creds is None:
        raise HTTPException(400, "등록된 키움 키가 없습니다. 먼저 키를 등록하세요")
    return broker.trade_api(creds, r)


@router.get("/settings")
def get_settings(s: SessionDep, user: CurrentUser):
    return _settings_out(_get_setting(s, user["id"]))


@router.put("/settings")
def put_settings(body: SettingsIn, s: SessionDep, user: CurrentUser):
    st = _get_setting(s, user["id"])
    changed = (st.env, st.max_order_amount, st.daily_loss_limit) != (body.env, body.max_order_amount,
                                                                     body.daily_loss_limit)
    st.env, st.max_order_amount, st.daily_loss_limit = body.env, body.max_order_amount, body.daily_loss_limit
    if changed and st.enabled:
        st.enabled = False
        st.disabled_reason = "설정이 바뀌어 다시 활성화가 필요합니다"
    s.commit()
    return _settings_out(st)


@router.post("/activate")
async def activate(body: ActivateIn, request: Request, s: SessionDep, user: CurrentUser):
    st = _get_setting(s, user["id"])
    if body.confirm.strip() != CONFIRM_TEXT[st.env]:
        raise HTTPException(400, f"확인 문구가 다릅니다. '{CONFIRM_TEXT[st.env]}'를 입력하세요")
    api = await asyncio.to_thread(_api_for, user["id"], st.env, request.app.state.redis)
    try:
        await api.balance()  # 키·계좌 연결 확인
    except KiwoomError as e:
        raise HTTPException(400, f"키움 연결 확인 실패: [{e.code}] {e.message}") from e
    st.enabled, st.disabled_reason = True, None
    st.activated_at = datetime.now(timezone.utc)
    s.commit()
    return _settings_out(st)


@router.post("/deactivate")
def deactivate(s: SessionDep, user: CurrentUser):
    st = _get_setting(s, user["id"])
    st.enabled, st.disabled_reason = False, "사용자가 정지했습니다"
    s.commit()
    return _settings_out(st)


@router.get("/account")
async def account(request: Request, s: SessionDep, user: CurrentUser):
    """키움 계좌 요약 + 보유 종목 + 예수금 + 오늘 손실"""
    st = _get_setting(s, user["id"])
    r = request.app.state.redis
    api = await asyncio.to_thread(_api_for, user["id"], st.env, r)
    try:
        bal, dep = await api.balance(), await api.deposit()
        daily = await risk.daily_loss(r, api, user["id"], st.env)
    except KiwoomError as e:
        raise HTTPException(502, f"키움 조회 실패: [{e.code}] {e.message}") from e
    holdings = [
        {
            "symbol": parse.code(h.get("stk_cd")), "name": (h.get("stk_nm") or "").strip(),
            "quantity": parse.qty(h.get("rmnd_qty")), "sellable": parse.qty(h.get("trde_able_qty")),
            "avg_price": parse.price(h.get("pur_pric")), "price": parse.price(h.get("cur_prc")),
            "eval_amount": parse.to_num(h.get("evlt_amt")), "profit": parse.to_num(h.get("evltv_prft")),
            "profit_rate": parse.to_num(h.get("prft_rt")),
        }
        for h in bal.get("acnt_evlt_remn_indv_tot") or []
    ]
    return {
        "env": st.env,
        "summary": {
            "total_purchase": parse.to_num(bal.get("tot_pur_amt")),
            "total_eval": parse.to_num(bal.get("tot_evlt_amt")),
            "total_profit": parse.to_num(bal.get("tot_evlt_pl")),
            "total_profit_rate": parse.to_num(bal.get("tot_prft_rt")),
            "estimated_assets": parse.to_num(bal.get("prsm_dpst_aset_amt")),
        },
        "cash": {
            "deposit": parse.to_num(dep.get("entr")),
            "orderable": parse.to_num(dep.get("ord_alow_amt")),
            "d2_deposit": parse.to_num(dep.get("d2_entra")),
        },
        "holdings": holdings,
        "today": daily,
    }


@router.post("/orders", status_code=201)
async def create_order(body: OrderIn, request: Request, user: CurrentUser):
    """직접 주문. 자동매매와 같은 위험 제한을 거친다. 막히면 status가 BLOCKED/REJECTED"""
    r = request.app.state.redis
    ref = body.price
    if ref is None:  # 시장가: 실시간 시세 → 없으면 현재가 조회 (장 마감 후·막 연 종목)
        raw = await r.hget("price:latest", body.symbol)
        if raw:
            ref = json.loads(raw)["price"]
        else:
            q = await get_quote(request.app.state, body.symbol)
            if not q or not q.get("price"):
                raise HTTPException(400, "시장가 주문 기준가를 알 수 없습니다 (현재가가 없어요)")
            ref = q["price"]
    return await broker.place_order(r, user["id"], body.symbol, body.side, body.quantity, ref,
                                    limit_price=body.price, reason={"manual": True})


@router.get("/orders")
async def list_orders(request: Request, s: SessionDep, user: CurrentUser, limit: int = 50, sync: bool = True):
    """주문 내역. sync=true면 키움 체결 현황으로 먼저 갱신"""
    if sync:
        try:
            await broker.sync_orders(request.app.state.redis, user["id"])
        except KiwoomError:
            pass  # 조회 실패해도 저장된 내역은 보여준다
    q = (select(KiwoomOrder).where(KiwoomOrder.user_id == user["id"])
         .order_by(KiwoomOrder.id.desc()).limit(min(limit, 500)))
    s.expire_all()
    return [broker.to_dict(o) for o in s.scalars(q)]


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: int, request: Request, s: SessionDep, user: CurrentUser):
    o = s.get(KiwoomOrder, order_id)
    if not o or o.user_id != user["id"]:
        raise HTTPException(404, "주문을 찾을 수 없습니다")
    if o.status not in broker.OPEN_STATUSES or not o.ord_no:
        raise HTTPException(400, "취소할 수 없는 주문입니다")
    api = await asyncio.to_thread(_api_for, user["id"], o.env, request.app.state.redis)
    try:
        res = await api.cancel(o.ord_no, o.symbol)
    except KiwoomError as e:
        raise HTTPException(400, f"취소 실패: [{e.code}] {e.message}") from e
    o.status = "CANCELLED"  # 일부 체결분은 filled_qty에 남는다
    o.message = str(res.get("return_msg") or "취소 접수")[:300]
    s.commit()
    return broker.to_dict(o)
