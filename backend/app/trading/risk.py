"""주문 전 위험 제한

1. 실거래가 켜져 있어야 한다 (활성화 확인 단계를 거친 경우만)
2. 1회 주문 금액 ≤ max_order_amount
3. 오늘 손실 < daily_loss_limit
   - 그날 첫 확인 때의 추정예탁자산(kt00018 prsm_dpst_aset_amt)을 Redis에 기준값으로 저장
   - 기준값 - 현재 추정예탁자산 = 오늘 손실. 한도에 닿으면 실거래를 자동으로 끈다
   - 한계: 그날 입출금이 있으면 손실로 계산될 수 있다
"""

from datetime import datetime

from app.kiwoom import parse
from app.kiwoom.client import KST

DAY_START_KEY = "kiwoom:daystart:{user_id}:{env}:{date}"


class RiskBlocked(Exception):
    def __init__(self, code: str, message: str, disable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.disable = disable  # True면 실거래를 자동으로 끈다


def check_order(setting, amount: float) -> None:
    if setting is None or not setting.enabled:
        raise RiskBlocked("disabled", "실거래가 활성화되어 있지 않습니다")
    if setting.max_order_amount and amount > setting.max_order_amount:
        raise RiskBlocked(
            "max_order_amount",
            f"1회 주문 한도 초과: {amount:,.0f}원 > {setting.max_order_amount:,}원",
        )


async def daily_loss(r, api, user_id: int, env: str) -> dict:
    """{start, current, loss} 오늘 기준 자산과 현재 자산"""
    bal = await api.balance()
    current = parse.to_num(bal.get("prsm_dpst_aset_amt"))
    key = DAY_START_KEY.format(user_id=user_id, env=env, date=datetime.now(KST).strftime("%Y%m%d"))
    await r.set(key, current, nx=True, ex=2 * 24 * 3600)  # 그날 첫 값만 저장
    start = float(await r.get(key))
    return {"start": start, "current": current, "loss": max(0.0, start - current)}


async def check_daily_loss(r, api, setting, user_id: int) -> dict:
    status = await daily_loss(r, api, user_id, setting.env)
    if setting.daily_loss_limit and status["loss"] >= setting.daily_loss_limit:
        raise RiskBlocked(
            "daily_loss_limit",
            f"일일 손실 한도 도달: {status['loss']:,.0f}원 ≥ {setting.daily_loss_limit:,}원 → 실거래를 껐습니다",
            disable=True,
        )
    return status
