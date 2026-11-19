"""시세 데이터 소스

- MockSource: 키움 API 키 없이 개발·시연할 수 있는 가상 시세 (랜덤워크 + 가끔 급등락)
- KisReplaySource: 한국투자 실제 과거 1분봉을 5초마다 Kafka로 재생
- KiwoomSource: 키움 실시간 시세 (플랫폼 키, 보고 있는 종목·전략 종목만 동적 구독)
"""

import asyncio
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


class KisReplaySource:
    """한국투자 과거 분봉을 자동매매 엔진용 실시간 시세처럼 재생한다."""

    def __init__(self, client=None, symbols: dict | None = None, interval: float | None = None, redis=None,
                 request_delay: float = 1.0):
        from app.core.config import settings
        from app.history.kis_minutes import KisMinuteClient

        self.client = client or KisMinuteClient(
            settings.kis_app_key,
            settings.kis_app_secret,
            settings.kis_base_url,
            settings.kis_replay_interval_sec,
            redis=redis,
        )
        if not self.client.enabled:
            raise RuntimeError(
                "한국투자 키가 없습니다. .env에 KIS_APP_KEY / KIS_APP_SECRET을 넣거나 "
                "MARKET_SOURCE=mock으로 실행하세요"
            )
        self.symbols = symbols or DEFAULT_SYMBOLS
        self.interval = settings.kis_replay_interval_sec if interval is None else max(0, interval)
        self.request_delay = max(0, request_delay)

    async def close(self) -> None:
        await self.client.close()

    async def stream(self):
        import logging

        log = logging.getLogger(__name__)
        bars = None
        while bars is None:
            try:
                loaded = {}
                # 토큰 중복 발급과 API 순간 호출 집중을 피하려고 종목별로 차례대로 준비한다.
                for symbol in self.symbols:
                    last_error = None
                    for attempt in range(3):
                        try:
                            loaded[symbol] = await self.client.minutes(symbol)
                            break
                        except Exception as exc:  # 종목별 순간 제한은 짧게 재시도
                            last_error = exc
                            if attempt < 2:
                                await asyncio.sleep(2)
                    if symbol not in loaded:
                        raise last_error or RuntimeError(f"{symbol} 분봉을 받지 못했습니다")
                    await asyncio.sleep(self.request_delay)
                bars = loaded
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # 외부 API 일시 제한이면 프로세스를 종료하지 않고 재시도
                log.warning("한국투자 분봉 준비 실패: %s → 60초 후 재시도", exc)
                await asyncio.sleep(60)
        cursor = 0
        while True:
            ticks = []
            for symbol, (name, _) in self.symbols.items():
                rows = bars[symbol]
                row = rows[cursor % len(rows)]
                ticks.append({
                    "symbol": symbol,
                    "name": name,
                    "price": round(row["price"]),
                    "volume": row["volume"],
                    "bid_size": 0,
                    "ask_size": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "market_timestamp": row["timestamp"],
                    "price_date": row["price_date"],
                    "source": "kis_replay",
                })
            yield ticks
            cursor += 1
            await asyncio.sleep(self.interval)


class KiwoomSource:
    """키움 실시간 시세 소스 (팀 키, WebSocket)

    - 구독 종목은 sync_every초마다 Redis(market:watch, market:strategy_symbols)를 보고 맞춘다
    - 체결·호가를 interval초 단위로 묶어 MockSource와 같은 형식의 시세로 내보낸다
    - 연결이 끊기면 1초부터 최대 60초까지 늘려가며 다시 접속한다
    """

    def __init__(self, redis, client=None, connect=None, interval: float = 1.0, sync_every: float = 2.0,
                 max_realtime: int | None = None, defaults: list[str] | None = None, stocks=None):
        from app.core.config import settings
        from app.kiwoom import platform
        from app.stocks.service import StockService

        self.redis = redis
        self.client = client or platform.team_client() or platform.open_team_client()
        if not self.client.enabled:
            raise RuntimeError(
                "키움 키가 없습니다. .env에 KIWOOM_APP_KEY / KIWOOM_SECRET_KEY를 넣거나 "
                "MARKET_SOURCE=mock으로 실행하세요"
            )
        self.stocks = stocks or StockService(redis, self.client)  # 종목 이름 (가상계좌 연습과 같은 Redis 캐시)
        self.connect = connect
        self.interval = interval
        self.sync_every = sync_every
        self.max_realtime = max_realtime or settings.kiwoom_max_realtime
        self.defaults = defaults if defaults is not None else platform.default_symbols()
        self.names: dict[str, str] = {}

    async def _sync(self, rt) -> None:
        from app.kiwoom.watch import desired_symbols

        desired = await desired_symbols(self.redis, self.defaults, self.max_realtime)
        if any(sym not in self.names for sym in desired):
            master = await self.stocks.master()
            for sym in desired:
                info = master.get(sym)
                self.names[sym] = info["name"] if info else DEFAULT_SYMBOLS.get(sym, (sym,))[0]
        await rt.sync(desired)

    @staticmethod
    async def _read(rt, agg) -> None:
        async for item in rt.messages():
            agg.feed(item)

    async def stream(self):
        """시세 목록을 interval마다 내보내는 async generator"""
        import asyncio
        import logging
        import time

        from app.kiwoom.realtime import KiwoomRealtime, TickAggregator

        log = logging.getLogger(__name__)
        backoff = 1.0
        while True:
            try:
                kwargs = {"connect": self.connect} if self.connect else {}
                async with KiwoomRealtime(self.client.env, self.client.token, **kwargs) as rt:
                    backoff = 1.0
                    agg = TickAggregator()
                    reader = asyncio.create_task(self._read(rt, agg))
                    last_sync = 0.0
                    try:
                        while True:
                            if reader.done():
                                reader.result()  # 오류가 있으면 여기서 올라감
                                raise ConnectionError("실시간 연결이 끊겼습니다")
                            if time.monotonic() - last_sync >= self.sync_every:
                                await self._sync(rt)
                                last_sync = time.monotonic()
                            await asyncio.sleep(self.interval)
                            ticks = agg.flush(lambda s: self.names.get(s, s))
                            if ticks:
                                yield ticks
                    finally:
                        reader.cancel()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - 끊기면 다시 접속
                log.warning("키움 실시간 오류: %s → %.0f초 후 재접속", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)


def create_source(name: str, redis=None):
    if name == "mock":
        return MockSource()
    if name == "kiwoom":
        return KiwoomSource(redis)
    if name == "kis_replay":
        return KisReplaySource(redis=redis)
    raise ValueError(f"알 수 없는 시세 소스: {name}")
