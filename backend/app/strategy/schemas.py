from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
