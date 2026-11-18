from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

IndicatorName = Literal["PRICE", "SMA", "EMA", "RSI", "BB_UPPER", "BB_MIDDLE", "BB_LOWER"]
Operator = Literal["<", "<=", ">", ">=", "cross_up", "cross_down"]


class Indicator(BaseModel):
    """보조지표 지정. 예) {"name": "RSI", "period": 14}"""

    name: IndicatorName
    period: int | None = Field(default=None, ge=2, le=200)
    k: float | None = Field(default=None, gt=0, le=5)  # 볼린저밴드 표준편차 배수


class Condition(BaseModel):
    """left op right. right는 숫자 또는 다른 지표.

    예) RSI(14) < 30
        PRICE cross_up SMA(20)   (현재가가 20 이동평균선을 상향 돌파)
    """

    left: Indicator
    op: Operator
    right: Indicator | float


class StrategyIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=20)
    side: Literal["buy", "sell"]
    conditions: list[Condition] = Field(min_length=1, max_length=10)
    quantity: int = Field(default=1, ge=1)
    cooldown_sec: int = Field(default=60, ge=0)
    enabled: bool = True
    account: Literal["paper", "kiwoom"] = "paper"  # kiwoom: 실거래 설정(서버·한도)으로 키움에 주문

    # 익절·손절(%): 평균 단가 대비 이만큼 오르거나(익절) 내리면(손절) 이 전략이 산 수량을 매도
    take_profit_pct: float | None = Field(default=None, gt=0, le=1000)
    stop_loss_pct: float | None = Field(default=None, gt=0, lt=100)

    @field_validator("account", mode="before")
    @classmethod
    def _default_account(cls, v):
        return v or "paper"  # 컬럼 추가 전에 만든 전략은 NULL

    @model_validator(mode="after")
    def _exit_only_for_paper_buy(self):
        if self.take_profit_pct is None and self.stop_loss_pct is None:
            return self
        if self.side != "buy":
            raise ValueError("익절·손절은 매수 전략에만 설정할 수 있어요")
        if self.account != "paper":
            raise ValueError("익절·손절은 아직 모의 주문 전략만 지원해요")
        return self


class StrategyOut(StrategyIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    strategy_id: int | None
    strategy_name: str
    symbol: str
    side: str
    quantity: int
    price: float
    status: str
    reason: dict
    created_at: datetime
