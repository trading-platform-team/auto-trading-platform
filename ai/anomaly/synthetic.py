"""평가용 합성 시세 (정답 라벨 포함)

backend MockSource와 같은 방식으로 시세를 만들되, 각 시세가
실제로 주입된 이상인지(label=1) 정상인지(label=0)를 함께 돌려준다.

이상 종류
- volume / price / orderbook : 하나의 지표가 크게 튀는 이상 (룰로 잡힘)
- combo : 거래량 2~2.8배 + 가격 1.5~2.5% + 호가 쏠림 0.35~0.5가 동시에 발생.
          각각은 룰 기준(3배, 3%, 0.6) 아래라서 룰은 놓치지만 함께 나타나면 비정상
"""

import random

from anomaly.rules import Bar


def generate(n: int, anomaly_rate: float = 0.02, seed: int = 0, start_price: float = 70000.0,
             kinds: tuple = ("volume", "price", "orderbook", "combo")):
    rng = random.Random(seed)
    price = start_price
    out: list[tuple[Bar, int, str]] = []
    for i in range(n):
        change = rng.gauss(0, 0.002)
        volume = int(rng.uniform(50, 150))
        bid, ask = rng.randint(400, 600), rng.randint(400, 600)
        label, kind = 0, "normal"
        if rng.random() < anomaly_rate:
            label, kind = 1, rng.choice(kinds)
            if kind == "volume":
                volume *= rng.randint(5, 10)
            elif kind == "price":
                change = rng.choice([-1, 1]) * rng.uniform(0.03, 0.06)
            elif kind == "orderbook":
                bid, ask = (bid * 8, ask) if rng.random() < 0.5 else (bid, ask * 8)
            else:  # combo: 매수세 몰림 (거래량↑ 가격↑ 매수잔량↑)
                volume = int(100 * rng.uniform(2.0, 2.8))
                change = rng.uniform(0.015, 0.025)
                imb = rng.uniform(0.35, 0.5)
                total = bid + ask
                bid, ask = int(total * (1 + imb) / 2), int(total * (1 - imb) / 2)
        price *= 1 + change
        out.append((Bar(str(i), round(price), volume, bid, ask), label, kind))
    return out
