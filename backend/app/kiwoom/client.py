"""키움 REST API 공용 클라이언트

- 접근 토큰(oauth2/token)을 받아 두고, 만료 5분 전에 자동으로 새로 받는다
- 호출 사이 최소 간격을 두어 호출 제한(429)에 걸리지 않게 한다
- return_code가 0이 아니면 KiwoomError (8005 토큰 만료는 토큰을 새로 받아 한 번 재시도)
- 연속조회: 응답 헤더 cont-yn / next-key 를 돌려주고, 다음 요청에 cont_key로 넘긴다

App Key·Secret은 .env(커밋 금지)에서만 읽는다. 로그에 키를 남기지 않는다.

실거래(사용자 본인 키)는 같은 KiwoomClient 위에 KiwoomTradeApi(계좌·주문)를 얹어 쓴다.
팀 키(.env)로 만든 KiwoomClient에는 주문 메서드가 없다.
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

KST = timezone(timedelta(hours=9))
TOKEN_EXPIRED = "8005"

REST_HOSTS = {"real": "https://api.kiwoom.com", "mock": "https://mockapi.kiwoom.com"}
WS_HOSTS = {"real": "wss://api.kiwoom.com:10000", "mock": "wss://mockapi.kiwoom.com:10000"}
WS_PATH = "/api/dostk/websocket"

PATH_ACNT = "/api/dostk/acnt"  # kt00018 계좌평가잔고, kt00001 예수금, kt00009 주문체결현황
PATH_ORDR = "/api/dostk/ordr"  # kt10000 매수, kt10001 매도, kt10003 취소


def env_of(base_url: str) -> str:
    """REST 주소 → 서버 구분 (real | mock)"""
    return "mock" if "mockapi" in base_url else "real"


class KiwoomError(RuntimeError):
    def __init__(self, message: str, code: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message


def num(value, signed: bool = False) -> float:
    """키움 응답 문자열 → 숫자. 현재가처럼 방향 부호(+/-)가 붙은 값은 signed=False면 절댓값"""
    s = str(value or "").strip().replace(",", "")
    if s in ("", "+", "-"):
        return 0.0
    try:
        n = float(s)
    except ValueError:
        return 0.0
    return n if signed else abs(n)


class KiwoomClient:
    def __init__(
        self,
        base_url: str,
        app_key: str,
        secret_key: str,
        transport: httpx.AsyncBaseTransport | None = None,
        min_interval: float = 0.25,
    ):
        self.app_key = app_key.strip()
        self.secret_key = secret_key.strip()
        self._http = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=10, transport=transport)
        self._token: str | None = None
        self._expires = datetime.min.replace(tzinfo=KST)
        self._token_lock = asyncio.Lock()
        self._call_lock = asyncio.Lock()
        self._min_interval = min_interval
        self._last_call = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.app_key and self.secret_key)

    @property
    def env(self) -> str:
        return env_of(str(self._http.base_url))

    async def token(self) -> str:
        """접근 토큰 (실시간 WebSocket LOGIN에 사용)"""
        return await self._token_value()

    async def close(self) -> None:
        await self._http.aclose()

    async def _post(self, path: str, **kw) -> httpx.Response:
        try:
            return await self._http.post(path, **kw)
        except httpx.HTTPError as e:  # 연결 실패·시간 초과
            raise KiwoomError(f"키움 서버에 연결할 수 없어요 ({type(e).__name__})") from e

    async def _token_value(self) -> str:
        async with self._token_lock:
            if self._token and datetime.now(KST) < self._expires - timedelta(minutes=5):
                return self._token
            res = await self._post(
                "/oauth2/token",
                json={"grant_type": "client_credentials", "appkey": self.app_key, "secretkey": self.secret_key},
                headers={"Content-Type": "application/json;charset=UTF-8"},
            )
            data = _json(res)
            if str(data.get("return_code", "0")) != "0" or not data.get("token"):
                raise KiwoomError(
                    f"토큰 발급 실패: {data.get('return_msg', res.status_code)}", str(data.get("return_code"))
                )
            self._token = data["token"]
            try:
                self._expires = datetime.strptime(data.get("expires_dt", ""), "%Y%m%d%H%M%S").replace(tzinfo=KST)
            except ValueError:
                self._expires = datetime.now(KST) + timedelta(hours=12)
            return self._token

    async def call(self, api_id: str, path: str, body: dict, cont_key: str = "") -> tuple[dict, dict]:
        """TR 호출 → (응답 본문, {"cont-yn", "next-key"})"""
        for attempt in range(2):
            token = await self._token_value()
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "api-id": api_id,
                "authorization": f"Bearer {token}",
            }
            if cont_key:
                headers["cont-yn"] = "Y"
                headers["next-key"] = cont_key
            async with self._call_lock:
                wait = self._min_interval - (time.monotonic() - self._last_call)
                if wait > 0:
                    await asyncio.sleep(wait)
                res = await self._post(path, json=body, headers=headers)
                self._last_call = time.monotonic()
            if res.status_code == 429 and attempt == 0:
                await asyncio.sleep(1)
                continue
            data = _json(res)
            code = str(data.get("return_code", "0"))
            if code == TOKEN_EXPIRED and attempt == 0:
                self._token = None
                continue
            if code != "0":
                raise KiwoomError(f"[{api_id}] {data.get('return_msg', '키움 API 오류')}", code)
            return data, {"cont-yn": res.headers.get("cont-yn", "N"), "next-key": res.headers.get("next-key", "")}
        raise KiwoomError(f"[{api_id}] 호출 제한으로 실패", "429")

    async def call_all(self, api_id: str, path: str, body: dict, list_key: str, max_pages: int = 30) -> list[dict]:
        """연속조회로 목록 전체 모으기"""
        items, cont = [], ""
        for _ in range(max_pages):
            data, head = await self.call(api_id, path, body, cont)
            items.extend(data.get(list_key) or [])
            if head["cont-yn"] != "Y" or not head["next-key"]:
                break
            cont = head["next-key"]
        return items


def _json(res: httpx.Response) -> dict:
    try:
        data = res.json()
    except ValueError as e:
        raise KiwoomError(f"키움 응답을 읽을 수 없어요 (HTTP {res.status_code})") from e
    if not isinstance(data, dict):
        raise KiwoomError(f"키움 응답 형식 오류 (HTTP {res.status_code})")
    return data


@dataclass(frozen=True)
class KiwoomCredentials:
    """사용자 본인 키 (실거래). env: real(api.kiwoom.com) | mock(mockapi.kiwoom.com)"""

    app_key: str
    secret_key: str
    env: str = "mock"

    def __post_init__(self):
        if self.env not in REST_HOSTS:
            raise ValueError(f"알 수 없는 키움 서버: {self.env}")

    @property
    def key_id(self) -> str:
        """로그·캐시 키에 쓰는 식별자 (키 원문은 남기지 않는다)"""
        return hashlib.sha256(f"{self.env}:{self.app_key}".encode()).hexdigest()[:16]

    def __repr__(self) -> str:  # 로그에 키가 찍히지 않도록
        return f"KiwoomCredentials(env={self.env}, key_id={self.key_id})"


class KiwoomTradeApi:
    """사용자 본인 키로 계좌 조회·주문 (KiwoomClient의 토큰·호출 간격·오류 처리를 그대로 사용)"""

    def __init__(self, creds: KiwoomCredentials, client: KiwoomClient | None = None,
                 transport: httpx.AsyncBaseTransport | None = None, min_interval: float = 0.25):
        self.creds = creds
        self.client = client or KiwoomClient(REST_HOSTS[creds.env], creds.app_key, creds.secret_key,
                                             transport=transport, min_interval=min_interval)

    @property
    def env(self) -> str:
        return self.creds.env

    async def token(self) -> str:
        return await self.client.token()

    async def aclose(self) -> None:
        await self.client.close()

    async def balance(self, exchange: str = "KRX") -> dict:
        """kt00018 계좌평가잔고 (합산). 보유 종목은 acnt_evlt_remn_indv_tot"""
        data, _ = await self.client.call("kt00018", PATH_ACNT, {"qry_tp": "1", "dmst_stex_tp": exchange})
        return data

    async def deposit(self) -> dict:
        """kt00001 예수금상세현황 (qry_tp 3: 추정조회)"""
        data, _ = await self.client.call("kt00001", PATH_ACNT, {"qry_tp": "3"})
        return data

    async def order(self, side: str, stk_cd: str, quantity: int, price: int | None = None,
                    exchange: str = "KRX") -> dict:
        """kt10000 매수 / kt10001 매도. price가 없으면 시장가(trde_tp 3), 있으면 지정가(0)

        return_code 0은 '접수'이며 체결이 아니다. 체결은 order_status로 확인한다.
        """
        if side not in ("buy", "sell"):
            raise ValueError("side는 buy 또는 sell")
        if quantity < 1:
            raise ValueError("수량은 1 이상")
        body = {
            "dmst_stex_tp": exchange,
            "stk_cd": stk_cd,
            "ord_qty": str(quantity),
            "ord_uv": "" if price is None else str(int(price)),
            "trde_tp": "3" if price is None else "0",
            "cond_uv": "",
        }
        data, _ = await self.client.call("kt10000" if side == "buy" else "kt10001", PATH_ORDR, body)
        return data

    async def cancel(self, orig_ord_no: str, stk_cd: str, quantity: int = 0, exchange: str = "KRX") -> dict:
        """kt10003 취소. quantity 0이면 잔량 전부"""
        body = {"dmst_stex_tp": exchange, "orig_ord_no": orig_ord_no, "stk_cd": stk_cd, "cncl_qty": str(quantity)}
        data, _ = await self.client.call("kt10003", PATH_ORDR, body)
        return data

    async def order_status(self, ord_dt: str = "", stk_cd: str = "", exchange: str = "%") -> list[dict]:
        """kt00009 계좌별 주문체결현황. 항목: ord_no, cntr_qty, cntr_uv, ord_qty ...

        ord_dt 빈 값이면 당일. dmst_stex_tp '%'는 전체 거래소.
        """
        body = {
            "ord_dt": ord_dt, "stk_bond_tp": "1", "mrkt_tp": "0", "sell_tp": "0", "qry_tp": "0",
            "stk_cd": stk_cd, "fr_ord_no": "", "dmst_stex_tp": exchange,
        }
        return await self.client.call_all("kt00009", PATH_ACNT, body, "acnt_ord_cntr_prst_array", max_pages=10)
