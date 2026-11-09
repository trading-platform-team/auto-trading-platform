"""TA-Lib 기반 보조지표 계산"""

import numpy as np
import talib

DEFAULT_PERIOD = {"SMA": 20, "EMA": 20, "RSI": 14, "BB_UPPER": 20, "BB_MIDDLE": 20, "BB_LOWER": 20}


def compute(name: str, closes: np.ndarray, period: int | None = None, k: float | None = None) -> np.ndarray:
    """종가 배열로 지표 시계열을 계산한다. 데이터가 부족한 앞부분은 NaN."""
    closes = np.asarray(closes, dtype=float)
    period = period or DEFAULT_PERIOD.get(name)

    if name == "PRICE":
        return closes
    if name == "SMA":
        return talib.SMA(closes, timeperiod=period)
    if name == "EMA":
        return talib.EMA(closes, timeperiod=period)
    if name == "RSI":
        return talib.RSI(closes, timeperiod=period)
    if name.startswith("BB_"):
        k = k or 2.0
        upper, middle, lower = talib.BBANDS(closes, timeperiod=period, nbdevup=k, nbdevdn=k)
        return {"BB_UPPER": upper, "BB_MIDDLE": middle, "BB_LOWER": lower}[name]
    raise ValueError(f"지원하지 않는 지표: {name}")


def label(ind: dict) -> str:
    """화면·로그 표시용 이름. 예) RSI(14), BB_LOWER(20,2.0)"""
    if ind["name"] == "PRICE":
        return "PRICE"
    period = ind.get("period") or DEFAULT_PERIOD.get(ind["name"])
    if ind["name"].startswith("BB_"):
        return f"{ind['name']}({period},{ind.get('k') or 2.0})"
    return f"{ind['name']}({period})"


def snapshot(closes) -> dict:
    """대시보드용 주요 지표 최신값"""
    closes = np.asarray(closes, dtype=float)

    def last(arr):
        v = arr[-1] if len(arr) else np.nan
        return None if np.isnan(v) else round(float(v), 2)

    if len(closes) == 0:
        return {}
    return {
        "price": last(closes),
        "sma5": last(compute("SMA", closes, 5)),
        "sma20": last(compute("SMA", closes, 20)),
        "rsi14": last(compute("RSI", closes, 14)),
        "bb_upper": last(compute("BB_UPPER", closes)),
        "bb_lower": last(compute("BB_LOWER", closes)),
    }
