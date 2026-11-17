"""체결 실시간 통보 (키움 WebSocket 00 주문체결)

- 실거래가 켜진 사용자의 키마다 WebSocket 하나를 열고 00을 등록한다
  (팀 모의 키처럼 여러 사용자가 같은 키를 쓰면 연결은 하나, 주문번호로 주문을 찾는다)
- 체결이 오면 kiwoom_orders를 바로 갱신하고 주문 주인에게 알림(Redis alerts → 화면 WebSocket·음성)
- 같은 체결이 여러 번 올 수 있어서 (주문번호, 체결번호)로 한 번만 반영한다
- 체결 수량은 911을 더하지 않고 '주문수량 - 미체결수량(902)'으로 계산한다
- 연결이 안 되거나 끊겨도 주문 내역 조회 때의 체결 동기화(sync_orders)가 그대로 동작한다
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app import db
from app.kiwoom import parse
from app.kiwoom.client import KiwoomCredentials
from app.kiwoom.realtime import TYPE_ORDER, KiwoomRealtime
from app.trading import broker, credentials
from app.trading.models import KiwoomOrder, KiwoomSetting

log = logging.getLogger("uvicorn.error")

FID_ORD_NO, FID_EXEC_NO, FID_QTY, FID_PRICE, FID_REMAIN = "9203", "909", "911", "910", "902"
SEEN_KEY = "kiwoom:exec:{env}:{ord_no}:{exec_no}"
GROUP = "9"  # 시세 구독(1)과 다른 그룹 번호


def _find_and_apply(env: str, ord_no: str, qty: int, price: float, remain: int | None) -> dict | None:
    with db.new_session() as s:
        candidates = s.scalars(select(KiwoomOrder).where(
            KiwoomOrder.env == env, KiwoomOrder.status.in_(broker.OPEN_STATUSES), KiwoomOrder.ord_no.is_not(None)))
        order = next((o for o in candidates if broker._norm_no(o.ord_no) == ord_no), None)
        if order is None:
            return None
        prev = order.filled_qty
        filled = order.quantity - remain if remain is not None else prev + qty
        filled = max(prev, min(order.quantity, filled))
        if filled == prev:
            return None
        added = filled - prev
        old_amount = (order.filled_price or 0) * prev
        order.filled_price = round((old_amount + price * added) / filled, 2) if price > 0 else order.filled_price
        order.filled_qty = filled
        order.status = "FILLED" if filled >= order.quantity else "PARTIAL"
        s.commit()
        out = broker.to_dict(order)
        out["added_qty"] = added
        return out


async def apply_execution(r, env: str, values: dict) -> dict | None:
    """00 메시지 하나 반영. 주문이 바뀌면 그 주문을, 아니면 None"""
    ord_no = broker._norm_no(values.get(FID_ORD_NO))
    qty = parse.qty(values.get(FID_QTY))
    if not ord_no or qty <= 0:  # 접수·확인 메시지 (체결 아님)
        return None
    exec_no = str(values.get(FID_EXEC_NO) or "").strip() or f"{qty}:{values.get(FID_PRICE)}:{values.get(FID_REMAIN)}"
    if not await r.set(SEEN_KEY.format(env=env, ord_no=ord_no, exec_no=exec_no), 1, nx=True, ex=2 * 24 * 3600):
        return None  # 이미 반영한 체결
    remain = parse.qty(values[FID_REMAIN]) if values.get(FID_REMAIN) not in (None, "") else None
    order = await asyncio.to_thread(_find_and_apply, env, ord_no, qty, parse.price(values.get(FID_PRICE)), remain)
    if order:
        from app.strategy.engine import push_alert

        side = "매수" if order["side"] == "buy" else "매도"
        done = "체결" if order["status"] == "FILLED" else f"일부 체결 {order['filled_qty']}/{order['quantity']}"
        px = parse.price(values.get(FID_PRICE))
        await push_alert(r, {
            "type": "order",
            "user_id": order["user_id"],
            "message": f"[키움 {done}] {order['symbol']} {order['added_qty']}주 {side} @ {px:,}원",
            "order": order,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    return order


def _wanted_credentials() -> dict[str, KiwoomCredentials]:
    with db.new_session() as s:
        enabled = list(s.scalars(select(KiwoomSetting).where(KiwoomSetting.enabled.is_(True))))
    wanted = {}
    for st in enabled:
        try:
            creds = credentials.get_credentials(st.user_id, st.env)
        except ValueError:
            continue
        if creds is not None:
            wanted[creds.key_id] = creds
    return wanted


class ExecutionWatcher:
    """실거래가 켜진 키마다 00 체결 WebSocket을 유지한다"""

    def __init__(self, r, connect=None, refresh_every: float = 10.0):
        self.r = r
        self.connect = connect
        self.refresh_every = refresh_every
        self.tasks: dict[str, asyncio.Task] = {}

    async def listen(self, creds: KiwoomCredentials) -> None:
        api = broker.trade_api(creds, self.r)
        kwargs = {"connect": self.connect} if self.connect else {}
        backoff = 1.0
        while True:
            try:
                async with KiwoomRealtime(creds.env, api.token, group=GROUP, **kwargs) as rt:
                    await rt.subscribe_account()
                    backoff = 1.0
                    log.info("체결 통보 연결 (%s)", creds)
                    async for item in rt.messages():
                        if item.get("type") == TYPE_ORDER:
                            await apply_execution(self.r, creds.env, item.get("values") or {})
                raise ConnectionError("체결 통보 연결이 끊겼습니다")
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("체결 통보 오류 (%s): %s → %.0f초 후 재접속", creds, e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    async def refresh(self) -> None:
        wanted = await asyncio.to_thread(_wanted_credentials)
        for key_id in list(self.tasks):
            if key_id not in wanted or self.tasks[key_id].done():
                self.tasks.pop(key_id).cancel()
        for key_id, creds in wanted.items():
            if key_id not in self.tasks:
                self.tasks[key_id] = asyncio.create_task(self.listen(creds))

    async def run_forever(self) -> None:
        try:
            while True:
                try:
                    await self.refresh()
                except Exception:  # noqa: BLE001
                    log.exception("체결 통보 대상 갱신 실패")
                await asyncio.sleep(self.refresh_every)
        finally:
            for t in self.tasks.values():
                t.cancel()
