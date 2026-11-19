"""가상계좌 연습용 호가창

한국투자 분봉 재생은 과거 체결가만 있고 그때의 호가는 없다. 그래서 재생 중인 가격을 기준으로
호가 단위에 맞춘 매도·매수 10단계 호가를 만든다.

호가 단위는 그 종목의 실제 분봉 가격들의 최대공약수로 정한다 (observed_tick). 실제 데이터에
31,875원·192,450원처럼 아래 표보다 촘촘한 가격이 나오기 때문에, 표는 분봉이 없을 때만 쓴다.

잔량은 그 분봉의 거래량에 비례하고, 같은 종목·같은 분봉이면 항상 같은 값이 나오도록
고정된 난수를 쓴다 (새로 고침해도 흔들리지 않게).
"""

import hashlib
import math
import random

LEVELS = 10

# 한국거래소 호가 가격 단위 (코스피·코스닥 공통, 2023년 1월 개편)
_TICKS = ((2_000, 1), (5_000, 5), (20_000, 10), (50_000, 50), (200_000, 100), (500_000, 500))


def tick_size(price: float) -> int:
    for limit, tick in _TICKS:
        if price < limit:
            return tick
    return 1_000


def observed_tick(prices: list[float]) -> int | None:
    """실제 체결 가격들의 최대공약수 (표의 호가 단위보다 크면 표 값). 가격이 없으면 None"""
    ints = [int(p) for p in prices if p and float(p).is_integer()]
    if not ints:
        return None
    return min(math.gcd(*ints), tick_size(max(ints)))


def is_valid_price(price: float, tick: int | None = None) -> bool:
    t = tick or tick_size(price)
    return price > 0 and float(price).is_integer() and int(price) % t == 0


def step(price: float, n: int, tick: int | None = None) -> int:
    """price에서 호가 n칸 위(+)·아래(−) 가격. tick이 없으면 표를 따라 구간마다 단위를 바꾼다."""
    p = int(price)
    if tick:
        return max(p + tick * n, tick)
    for _ in range(abs(n)):
        if n > 0:
            p += tick_size(p)
        else:
            p -= tick_size(p - 1) if p > 1 else 0
    return max(p, 1)


def align(price: float, tick: int | None = None) -> int:
    """호가 단위에 맞지 않는 가격을 가까운 아래 호가로 내린다"""
    p = int(price)
    t = tick or tick_size(p)
    return max(p - p % t, 1)


def build(symbol: str, quote: dict, tick: int | None = None) -> dict:
    """quote(재생 분봉: price, volume, timestamp)로 호가창을 만든다.

    매도 1호가 = 현재가, 매수 1호가 = 현재가 한 칸 아래. 시장가로 사면 현재가에 체결되는 것과 맞춘다.
    """
    price = align(quote["price"], tick)
    seed = hashlib.sha256(f"{symbol}|{quote.get('timestamp') or price}".encode()).hexdigest()
    rnd = random.Random(int(seed[:16], 16))
    base = max(int(quote.get("volume") or 0), 100)

    def size(level: int) -> int:
        # 현재가에 가까울수록 조금 적고, 멀어질수록 쌓이는 모양
        return max(int(base * (0.4 + 0.12 * level) * rnd.uniform(0.5, 1.5)), 1)

    asks = [{"price": step(price, i, tick), "quantity": size(i)} for i in range(LEVELS)]
    bids = [{"price": step(price, -(i + 1), tick), "quantity": size(i)} for i in range(LEVELS)]
    return {
        "symbol": symbol,
        "price": price,
        "tick": tick or tick_size(price),
        "asks": asks[::-1],  # 화면 위쪽이 높은 가격
        "bids": bids,
        "total_ask": sum(a["quantity"] for a in asks),
        "total_bid": sum(b["quantity"] for b in bids),
        "timestamp": quote.get("timestamp"),
        "source": quote.get("source"),
        "simulated": True,
    }
