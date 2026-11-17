"""키움 실시간 시세 WebSocket

흐름: 접속 → LOGIN(토큰) → REG(종목, 0B 체결 + 0D 호가잔량) → REAL 메시지 수신
- 서버가 보내는 PING은 그대로 돌려보내야 연결이 유지된다 (websockets 자체 ping은 끈다)
- REAL 메시지에는 return_code가 없다. LOGIN/REG/REMOVE 응답에만 있다
- values의 키는 FID 번호 문자열

FID (공식 명세 기준, 키 발급 후 확인 필요)
- 0B 주식체결: 10 현재가, 15 거래량(+매수/-매도 체결), 13 누적거래량, 20 체결시간
- 0D 주식호가잔량: 121 매도호가총잔량, 125 매수호가총잔량
"""

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from app.kiwoom import parse
from app.kiwoom.client import WS_HOSTS, WS_PATH, KiwoomError

log = logging.getLogger(__name__)

TYPE_TRADE = "0B"
TYPE_BOOK = "0D"
FID_PRICE, FID_VOLUME = "10", "15"
FID_ASK_TOTAL, FID_BID_TOTAL = "121", "125"
REG_CHUNK = 30  # 한 번에 등록할 종목 수 (몰아서 보내지 않기)


def _default_connect(url: str):
    import websockets  # collector에서만 필요

    return websockets.connect(url, ping_interval=None, max_size=2**22)


class KiwoomRealtime:
    """WebSocket 연결 하나. connect 인자는 테스트에서 가짜 연결로 바꿀 수 있다."""

    def __init__(self, env: str, token_provider: Callable[[], Awaitable[str]], connect=_default_connect,
                 group: str = "1"):
        self.url = WS_HOSTS[env] + WS_PATH
        self.token_provider = token_provider
        self._connect = connect
        self.group = group
        self.ws = None
        self.subscribed: set[str] = set()

    async def __aenter__(self):
        self.ws = await self._connect(self.url).__aenter__()
        await self._send({"trnm": "LOGIN", "token": await self.token_provider()})
        while True:  # LOGIN 응답 대기 (그 사이 PING이 올 수 있음)
            msg = json.loads(await self.ws.recv())
            if msg.get("trnm") == "PING":
                await self._send(msg)
                continue
            if msg.get("trnm") == "LOGIN":
                if str(msg.get("return_code", "0")) != "0":
                    raise KiwoomError(msg.get("return_msg", "실시간 로그인 실패"), str(msg.get("return_code")))
                break
        self.subscribed = set()
        log.info("키움 실시간 접속 성공")
        return self

    async def __aexit__(self, *exc):
        if self.ws is not None:
            await self.ws.close()
            self.ws = None

    async def _send(self, msg: dict) -> None:
        await self.ws.send(json.dumps(msg))

    async def subscribe(self, codes: list[str]) -> None:
        new = [c for c in codes if c not in self.subscribed]
        for i in range(0, len(new), REG_CHUNK):
            chunk = new[i:i + REG_CHUNK]
            await self._send({"trnm": "REG", "grp_no": self.group, "refresh": "1",
                              "data": [{"item": chunk, "type": [TYPE_TRADE, TYPE_BOOK]}]})
            self.subscribed.update(chunk)

    async def unsubscribe(self, codes: list[str]) -> None:
        old = [c for c in codes if c in self.subscribed]
        for i in range(0, len(old), REG_CHUNK):
            chunk = old[i:i + REG_CHUNK]
            await self._send({"trnm": "REMOVE", "grp_no": self.group,
                              "data": [{"item": chunk, "type": [TYPE_TRADE, TYPE_BOOK]}]})
            self.subscribed.difference_update(chunk)

    async def sync(self, desired: list[str]) -> None:
        """원하는 종목 목록과 맞추기 (빠진 것 해제, 새로운 것 등록)"""
        want = set(desired)
        await self.unsubscribe(sorted(self.subscribed - want))
        await self.subscribe([c for c in desired if c not in self.subscribed])

    async def messages(self) -> AsyncIterator[dict]:
        """REAL 데이터 항목을 하나씩 내보낸다. PING 응답과 등록 결과 로그는 여기서 처리"""
        async for raw in self.ws:
            msg = json.loads(raw)
            trnm = msg.get("trnm")
            if trnm == "PING":
                await self._send(msg)
            elif trnm == "REAL":
                for item in msg.get("data") or []:
                    yield item
            elif trnm in ("REG", "REMOVE") and str(msg.get("return_code", "0")) != "0":
                log.warning("실시간 %s 실패: [%s] %s", trnm, msg.get("return_code"), msg.get("return_msg"))


class TickAggregator:
    """체결(0B)·호가(0D)를 모아 종목별로 interval마다 시세 1건을 만든다.

    실제 체결은 1초에 수십 건씩 올 수 있어서, 모의 시세와 같은 형식(1초 1건, 그동안의 거래량 합)으로 묶는다.
    → Kafka·전략 엔진·AI 이상탐지는 시세 소스와 상관없이 그대로 동작한다.
    """

    def __init__(self):
        self.book: dict[str, tuple[int, int]] = {}  # 종목 → (매수총잔량, 매도총잔량)
        self.pending: dict[str, dict] = {}  # 종목 → {price, volume}

    def feed(self, item: dict) -> None:
        sym = parse.code(item.get("item"))
        values = item.get("values") or {}
        kind = item.get("type")
        if kind == TYPE_BOOK:
            self.book[sym] = (parse.qty(values.get(FID_BID_TOTAL)), parse.qty(values.get(FID_ASK_TOTAL)))
        elif kind == TYPE_TRADE:
            px = parse.price(values.get(FID_PRICE))
            if px <= 0:
                return
            p = self.pending.setdefault(sym, {"price": px, "volume": 0})
            p["price"] = px
            p["volume"] += parse.qty(values.get(FID_VOLUME))

    def flush(self, name_of: Callable[[str], str]) -> list[dict]:
        from app.market.sources import make_tick

        ticks = []
        for sym, p in self.pending.items():
            bid, ask = self.book.get(sym, (0, 0))
            ticks.append(make_tick(sym, name_of(sym), p["price"], p["volume"], bid, ask))
        self.pending.clear()
        return ticks
