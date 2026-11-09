"""시세 데이터 소스

- MockSource: 키움 API 키 없이 개발·시연할 수 있는 가상 시세 (랜덤워크 + 가끔 급등락)
- KiwoomSource: 키움 REST API 연동 (키 발급 후 구현, Issue #3)
"""

import random
from datetime import datetime, timezone

DEFAULT_SYMBOLS = {
    "005930": ("삼성전자", 70000),
    "000660": ("SK하이닉스", 180000),
    "035420": ("NAVER", 190000),
    "005380": ("현대차", 240000),
    "035720": ("카카오", 40000),
}


def make_tick(symbol: str, name: str, price: float, volume: int, bid_size: int, ask_size: int) -> dict:
    return {
        "symbol": symbol,
        "name": name,
        "price": round(price),
        "volume": volume,
        "bid_size": bid_size,
        "ask_size": ask_size,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class MockSource:
    """가상 시세 생성기. anomaly_rate 확률로 거래량 급증·가격 급변·호가 쏠림·복합 이상을 섞는다."""

    def __init__(self, symbols: dict | None = None, anomaly_rate: float = 0.02, seed: int | None = None):
        self.symbols = symbols or DEFAULT_SYMBOLS
        self.prices = {s: float(p) for s, (_, p) in self.symbols.items()}
        self.anomaly_rate = anomaly_rate
        self.rng = random.Random(seed)

    def next_ticks(self) -> list[dict]:
        ticks = []
        for symbol, (name, _) in self.symbols.items():
            change = self.rng.gauss(0, 0.002)  # 평소 ±0.2% 수준 변동
            volume = int(self.rng.uniform(50, 150))
            bid, ask = self.rng.randint(400, 600), self.rng.randint(400, 600)

            if self.rng.random() < self.anomaly_rate:  # 이상 이벤트
                kind = self.rng.choice(["volume", "price", "orderbook", "combo"])
                if kind == "volume":
                    volume *= self.rng.randint(5, 10)
                elif kind == "price":
                    change = self.rng.choice([-1, 1]) * self.rng.uniform(0.03, 0.06)
                elif kind == "orderbook":
                    bid, ask = (bid * 8, ask) if self.rng.random() < 0.5 else (bid, ask * 8)
                else:  # 복합: 각각은 룰 기준 미만이지만 동시에 발생 (AI 모델만 탐지)
                    volume = int(100 * self.rng.uniform(2.0, 2.8))
                    change = self.rng.uniform(0.015, 0.025)
                    imb, total = self.rng.uniform(0.35, 0.5), bid + ask
                    bid, ask = int(total * (1 + imb) / 2), int(total * (1 - imb) / 2)

            self.prices[symbol] = max(1.0, self.prices[symbol] * (1 + change))
            ticks.append(make_tick(symbol, name, self.prices[symbol], volume, bid, ask))
        return ticks


class KiwoomSource:
    """키움 REST API 시세 소스 (TODO: Issue #3에서 구현)"""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError("키움 API 키 발급 후 구현 예정")


def create_source(name: str):
    if name == "mock":
        return MockSource()
    if name == "kiwoom":
        return KiwoomSource()
    raise ValueError(f"알 수 없는 시세 소스: {name}")
