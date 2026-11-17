"""키움 REST API 공용 클라이언트

- 접근 토큰(oauth2/token)을 받아 두고, 만료 5분 전에 자동으로 새로 받는다
- 호출 사이 최소 간격을 두어 호출 제한(429)에 걸리지 않게 한다
- return_code가 0이 아니면 KiwoomError (8005 토큰 만료는 토큰을 새로 받아 한 번 재시도)
- 연속조회: 응답 헤더 cont-yn / next-key 를 돌려주고, 다음 요청에 cont_key로 넘긴다

App Key·Secret은 .env(커밋 금지)에서만 읽는다. 로그에 키를 남기지 않는다.
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone

import httpx

KST = timezone(timedelta(hours=9))
TOKEN_EXPIRED = "8005"


class KiwoomError(RuntimeError):
    def __init__(self, message: str, code: str = ""):
        super().__init__(message)
        self.code = code


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


def _json(res: httpx.Response) -> dict:
    try:
        data = res.json()
    except ValueError as e:
        raise KiwoomError(f"키움 응답을 읽을 수 없어요 (HTTP {res.status_code})") from e
    if not isinstance(data, dict):
        raise KiwoomError(f"키움 응답 형식 오류 (HTTP {res.status_code})")
    return data
