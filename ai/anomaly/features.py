"""이상탐지 모델 입력 특징(feature) 계산

최근 시세 구간에서 마지막 시세의 특징 4가지를 만든다.
- ret        직전 대비 수익률(%)
- vol_ratio  최근 평균 대비 거래량 배수
- imbalance  호가 불균형 (-1 ~ 1)
- volatility 최근 수익률 표준편차(%)
"""

import numpy as np

from anomaly.rules import Bar

FEATURES = ["ret", "vol_ratio", "imbalance", "volatility"]
FEATURE_KO = {"ret": "가격 변동", "vol_ratio": "거래량", "imbalance": "호가 불균형", "volatility": "변동성"}


def extract(bars: list[Bar], window: int = 20) -> np.ndarray | None:
    if len(bars) < 3:
        return None
    recent = bars[-(window + 1):]
    prices = np.array([b.price for b in recent], dtype=float)
    volumes = np.array([b.volume for b in recent], dtype=float)
    rets = np.diff(prices) / prices[:-1] * 100

    last = bars[-1]
    total = last.bid_size + last.ask_size
    imbalance = (last.bid_size - last.ask_size) / total if total > 0 else 0.0
    past_vol = volumes[:-1].mean()
    vol_ratio = volumes[-1] / past_vol if past_vol > 0 else 1.0
    volatility = rets[:-1].std() if len(rets) > 2 else 0.0

    return np.array([rets[-1], vol_ratio, imbalance, volatility], dtype=float)
