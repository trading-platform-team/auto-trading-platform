"""룰 기반 이상거래 탐지 베이스라인

AI 모델과 비교할 기준선 역할을 한다.
- 거래량 급증: 최근 window개 평균 대비 거래량이 volume_ratio배 이상
- 가격 급변: 직전 대비 등락률 절댓값이 price_change_pct% 이상
- 호가 불균형: (매수잔량-매도잔량)/(매수잔량+매도잔량) 절댓값이 imbalance 이상
"""

from dataclasses import dataclass, field
from statistics import mean


@dataclass
class Bar:
    timestamp: str
    price: float
    volume: float
    bid_size: float = 0.0  # 매수 호가 총잔량
    ask_size: float = 0.0  # 매도 호가 총잔량


@dataclass
class RuleConfig:
    window: int = 20
    volume_ratio: float = 3.0
    price_change_pct: float = 3.0
    imbalance: float = 0.6


@dataclass
class Anomaly:
    timestamp: str
    type: str  # volume_spike | price_jump | orderbook_imbalance
    value: float
    message: str = field(default="")


def check_bar(bars: list[Bar], i: int, cfg: RuleConfig) -> list[Anomaly]:
    """i번째 시세 한 건을 룰로 검사한다."""
    bar = bars[i]
    found: list[Anomaly] = []

    # 1) 거래량 급증
    past = bars[max(0, i - cfg.window):i]
    if len(past) >= 3:
        avg = mean(b.volume for b in past)
        if avg > 0 and bar.volume / avg >= cfg.volume_ratio:
            ratio = bar.volume / avg
            found.append(Anomaly(bar.timestamp, "volume_spike", round(ratio, 2), f"거래량이 평균 대비 {ratio:.1f}배"))

    # 2) 가격 급변
    if i > 0 and bars[i - 1].price > 0:
        pct = (bar.price - bars[i - 1].price) / bars[i - 1].price * 100
        if abs(pct) >= cfg.price_change_pct:
            found.append(Anomaly(bar.timestamp, "price_jump", round(pct, 2), f"직전 대비 {pct:+.2f}% 변동"))

    # 3) 호가 불균형
    total = bar.bid_size + bar.ask_size
    if total > 0:
        imb = (bar.bid_size - bar.ask_size) / total
        if abs(imb) >= cfg.imbalance:
            side = "매수" if imb > 0 else "매도"
            found.append(Anomaly(bar.timestamp, "orderbook_imbalance", round(imb, 2), f"{side} 잔량 쏠림 ({imb:+.2f})"))

    return found


def detect(bars: list[Bar], cfg: RuleConfig | None = None) -> list[Anomaly]:
    """전체 구간 검사 (백테스트·분석용)"""
    cfg = cfg or RuleConfig()
    return [a for i in range(len(bars)) for a in check_bar(bars, i, cfg)]


def detect_last(bars: list[Bar], cfg: RuleConfig | None = None) -> list[Anomaly]:
    """가장 최근 시세만 검사 (실시간용)"""
    return check_bar(bars, len(bars) - 1, cfg or RuleConfig()) if bars else []
