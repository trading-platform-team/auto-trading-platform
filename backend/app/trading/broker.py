"""KiwoomBroker: 사용자 키로 키움에 주문

place_order 순서
  설정 확인 → 1회 주문 한도 → 사용자 키 조회 → 일일 손실 한도(잔고 조회) → 키움 주문 → 기록
  어느 단계에서 막혀도 주문 기록(BLOCKED/REJECTED)과 사유를 남긴다.
  키움 return_code 0은 '접수'이므로 상태는 SUBMITTED. 체결은 sync_orders로 갱신한다.
"""

import asyncio
import logging

from sqlalchemy import select

from app import db
from app.core.config import settings
from app.kiwoom import parse, platform
from app.kiwoom.client import KiwoomCredentials, KiwoomError, KiwoomTradeApi
from app.trading import credentials, risk
from app.trading.models import KiwoomOrder, KiwoomSetting

log = logging.getLogger("uvicorn.error")

OPEN_STATUSES = ("SUBMITTED", "PARTIAL")
_apis: dict[str, KiwoomTradeApi] = {}
transport = None  # 테스트에서 가짜 키움 서버(httpx.MockTransport)로 바꾼다


def trade_api(creds: KiwoomCredentials, r=None) -> KiwoomTradeApi:
    """키마다 클라이언트 하나를 재사용 (토큰·호출 간격 공유). 팀 키면 서버의 팀 KiwoomClient를 같이 쓴다"""
    api = _apis.get(creds.key_id)
    if api is None or api.creds != creds:
        shared = platform.team_client() if creds == platform.team_credentials() else None
        per_sec = settings.kiwoom_rest_per_sec
        api = KiwoomTradeApi(creds, client=shared, transport=transport, min_interval=1 / per_sec if per_sec > 0 else 0)
        _apis[creds.key_id] = api
    return api


def reset_apis() -> None:
    _apis.clear()


def to_dict(o: KiwoomOrder) -> dict:
    return {
        "id": o.id, "user_id": o.user_id, "strategy_id": o.strategy_id, "strategy_name": o.strategy_name,
        "env": o.env, "symbol": o.symbol, "side": o.side, "quantity": o.quantity, "order_type": o.order_type,
        "price": o.price, "ord_no": o.ord_no, "status": o.status, "filled_qty": o.filled_qty,
        "filled_price": o.filled_price, "message": o.message, "reason": o.reason,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


# ---------- DB (동기, to_thread로 호출) ----------
def load_setting(user_id: int) -> KiwoomSetting | None:
    with db.new_session() as s:
        return s.get(KiwoomSetting, user_id)


def disable(user_id: int, reason: str) -> None:
    with db.new_session() as s:
        st = s.get(KiwoomSetting, user_id)
        if st and st.enabled:
            st.enabled = False
            st.disabled_reason = reason[:200]
            s.commit()


def _save(order: KiwoomOrder) -> dict:
    with db.new_session() as s:
        s.add(order)
        s.commit()
        s.refresh(order)
        return to_dict(order)


async def place_order(
    r, user_id: int, symbol: str, side: str, quantity: int, ref_price: float,
    limit_price: int | None = None, strategy_id: int | None = None, strategy_name: str | None = None,
    reason: dict | None = None,
) -> dict:
    setting = await asyncio.to_thread(load_setting, user_id)
    env = setting.env if setting else "mock"
    order = KiwoomOrder(
        user_id=user_id, strategy_id=strategy_id, strategy_name=strategy_name, env=env, symbol=symbol, side=side,
        quantity=quantity, order_type="market" if limit_price is None else "limit",
        price=float(limit_price if limit_price is not None else ref_price), reason=dict(reason or {}),
    )
    try:
        risk.check_order(setting, quantity * order.price)
        creds = await asyncio.to_thread(credentials.get_credentials, user_id, env)
        if creds is None:
            raise risk.RiskBlocked("no_credentials", "등록된 키움 키가 없습니다")
        api = trade_api(creds, r)
        order.reason["daily"] = await risk.check_daily_loss(r, api, setting, user_id)
        res = await api.order(side, symbol, quantity, limit_price)
        order.ord_no = str(res.get("ord_no") or "") or None
        order.status = "SUBMITTED"
        order.message = str(res.get("return_msg") or "주문 접수")[:300]
    except risk.RiskBlocked as e:
        order.status, order.message = "BLOCKED", e.message[:300]
        order.reason["blocked"] = e.code
        if e.disable:
            await asyncio.to_thread(disable, user_id, e.message)
    except KiwoomError as e:
        order.status, order.message = "REJECTED", f"[{e.code}] {e.message}"[:300]
    except ValueError as e:
        order.status, order.message = "REJECTED", str(e)[:300]
    saved = await asyncio.to_thread(_save, order)
    log.info("키움 주문 %s: 사용자 %s %s %s %d주 (%s)",
             saved["status"], user_id, symbol, side, quantity, saved["message"])
    return saved


# ---------- 체결 동기화 ----------
def _norm_no(no) -> str:
    return str(no or "").strip().lstrip("0")


def summarize_fills(rows: list[dict]) -> dict[str, tuple[int, float | None]]:
    """kt00009 행(체결 건별일 수 있음) → 주문번호별 (체결수량 합, 평균 체결가)"""
    acc: dict[str, list[float]] = {}
    for row in rows:
        no = _norm_no(row.get("ord_no"))
        q = parse.qty(row.get("cntr_qty"))
        if not no or q <= 0:
            continue
        a = acc.setdefault(no, [0, 0.0])
        a[0] += q
        a[1] += q * parse.price(row.get("cntr_uv"))
    return {no: (int(q), round(amt / q, 2) if q else None) for no, (q, amt) in acc.items()}


def _open_orders(user_id: int) -> list[KiwoomOrder]:
    with db.new_session() as s:
        return list(s.scalars(select(KiwoomOrder).where(
            KiwoomOrder.user_id == user_id, KiwoomOrder.status.in_(OPEN_STATUSES), KiwoomOrder.ord_no.is_not(None))))


def _apply_fills(order_ids: list[int], fills: dict[str, tuple[int, float | None]]) -> int:
    changed = 0
    with db.new_session() as s:
        for oid in order_ids:
            o = s.get(KiwoomOrder, oid)
            got = fills.get(_norm_no(o.ord_no))
            if not got or got[0] == o.filled_qty:
                continue
            o.filled_qty, o.filled_price = got
            o.status = "FILLED" if o.filled_qty >= o.quantity else "PARTIAL"
            changed += 1
        s.commit()
    return changed


async def sync_orders(r, user_id: int) -> int:
    """접수·일부체결 주문을 키움 당일 체결 현황으로 갱신. 바뀐 주문 수를 반환"""
    opened = await asyncio.to_thread(_open_orders, user_id)
    if not opened:
        return 0
    by_env: dict[str, list[KiwoomOrder]] = {}
    for o in opened:
        by_env.setdefault(o.env, []).append(o)
    changed = 0
    for env, orders in by_env.items():
        creds = await asyncio.to_thread(credentials.get_credentials, user_id, env)
        if creds is None:
            continue
        rows = await trade_api(creds, r).order_status()
        changed += await asyncio.to_thread(_apply_fills, [o.id for o in orders], summarize_fills(rows))
    return changed
