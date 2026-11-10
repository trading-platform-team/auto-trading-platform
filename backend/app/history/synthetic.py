"""가상 과거 일봉 생성기

키움 API(일봉 조회) 연동 전까지 타임머신·백테스트를 시연하기 위한 데이터.
실제 시세가 아니며, 화면과 API 응답에 source="synthetic"으로 표시한다.

- 영업일(월~금)만 생성
- 상승장 / 하락장 / 횡보장 구간이 40~90일마다 바뀜 → 전략마다 성과 차이가 드러나도록
- 가끔 갭 상승·하락 + 거래량 급증 이벤트 → 타임머신에서 이상거래 표시
- 종목코드로 seed를 정해서 항상 같은 데이터가 만들어진다
"""

import math
import random
from datetime import date, timedelta

REGIMES = {"bull": (0.0012, 0.016), "bear": (-0.0011, 0.019), "sideways": (0.0, 0.012)}  # (일간 기대수익, 변동성)


def business_days(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def generate_daily(symbol: str, base_price: float, start: date, end: date) -> list[dict]:
    rng = random.Random(int(symbol) if symbol.isdigit() else hash(symbol))
    price = float(base_price)
    regime, left = "sideways", 0
    base_volume = rng.randint(800_000, 1_500_000)
    bars = []

    for d in business_days(start, end):
        if left <= 0:
            regime, left = rng.choice(list(REGIMES)), rng.randint(40, 90)
        left -= 1
        mu, sigma = REGIMES[regime]

        ret = rng.gauss(mu, sigma)
        volume = base_volume * rng.uniform(0.6, 1.4) * (1 + abs(ret) * 15)
        if rng.random() < 0.015:  # 갭 이벤트
            ret = rng.choice([-1, 1]) * rng.uniform(0.05, 0.09)
            volume *= rng.uniform(3, 6)

        open_ = price * (1 + rng.gauss(0, sigma / 3))
        close = max(100.0, price * math.exp(ret))
        high = max(open_, close) * (1 + abs(rng.gauss(0, sigma / 2)))
        low = min(open_, close) * (1 - abs(rng.gauss(0, sigma / 2)))
        bars.append(
            {
                "symbol": symbol,
                "date": d,
                "open": round(open_),
                "high": round(high),
                "low": round(low),
                "close": round(close),
                "volume": int(volume),
            }
        )
        price = close
    return bars
