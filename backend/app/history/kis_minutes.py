"""한국투자 Open API 과거 분봉을 교육용 시세처럼 재생한다.

주문 API는 사용하지 않는다. 최근 거래일의 1분봉을 받아 5초마다 다음 봉으로
이동시키므로 여러 사용자가 같은 재생 시세로 안전하게 가상 매매할 수 있다.
"""

import time
from datetime import date, timedelta

import httpx


class KisMinuteError(RuntimeError):
    pass


class KisMinuteClient:
    def __init__(self, app_key: str, app_secret: str, base_url: str, interval: float = 5.0,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.app_key = app_key.strip()
        self.app_secret = app_secret.strip()
        self.interval = max(1.0, interval)
        self.client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=20, transport=transport)
        self._token: tuple[float, str] | None = None
        self._cache: dict[str, tuple[float, list[dict]]] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.app_key and self.app_secret)

    async def close(self) -> None:
        await self.client.aclose()

    async def _access_token(self) -> str:
        if self._token and self._token[0] > time.monotonic():
            return self._token[1]
        try:
            response = await self.client.post("/oauth2/tokenP", json={
                "grant_type": "client_credentials", "appkey": self.app_key, "appsecret": self.app_secret,
            })
            response.raise_for_status()
            payload = response.json()
            token = payload["access_token"]
            ttl = max(60, int(payload.get("expires_in", 86400)) - 60)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise KisMinuteError(f"한국투자 인증 실패: {exc}") from exc
        self._token = (time.monotonic() + ttl, token)
        return token

    async def _request_day(self, symbol: str, day: date) -> list[dict]:
        token = await self._access_token()
        try:
            response = await self.client.get(
                "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice",
                headers={
                    "authorization": f"Bearer {token}", "appkey": self.app_key,
                    "appsecret": self.app_secret, "tr_id": "FHKST03010230", "custtype": "P",
                },
                params={
                    "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol,
                    "FID_INPUT_DATE_1": day.strftime("%Y%m%d"), "FID_INPUT_HOUR_1": "153000",
                    "FID_PW_DATA_INCU_YN": "Y", "FID_FAKE_TICK_INCU_YN": "N",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise KisMinuteError(f"한국투자 분봉 조회 실패: {exc}") from exc
        if str(payload.get("rt_cd")) != "0":
            raise KisMinuteError(payload.get("msg1") or "한국투자 분봉 응답 오류")
        rows = []
        for raw in payload.get("output2") or []:
            try:
                hhmmss = str(raw.get("stck_cntg_hour") or "").zfill(6)
                rows.append({
                    "timestamp": f"{day.isoformat()}T{hhmmss[:2]}:{hhmmss[2:4]}:{hhmmss[4:]}",
                    "price": float(raw["stck_prpr"]),
                    "open": float(raw.get("stck_oprc") or raw["stck_prpr"]),
                    "high": float(raw.get("stck_hgpr") or raw["stck_prpr"]),
                    "low": float(raw.get("stck_lwpr") or raw["stck_prpr"]),
                    "volume": int(float(raw.get("cntg_vol") or 0)),
                    "price_date": day.isoformat(), "source": "kis_replay",
                })
            except (KeyError, TypeError, ValueError):
                continue
        return sorted(rows, key=lambda row: row["timestamp"])

    async def minutes(self, symbol: str) -> list[dict]:
        cached = self._cache.get(symbol)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        day = date.today()
        rows = []
        for offset in range(8):
            rows = await self._request_day(symbol, day - timedelta(days=offset))
            if rows:
                break
        if not rows:
            raise KisMinuteError("최근 거래일 분봉이 없습니다")
        self._cache[symbol] = (time.monotonic() + 600, rows)
        return rows

    async def replay_quote(self, symbol: str) -> dict | None:
        if not self.enabled:
            return None
        rows = await self.minutes(symbol)
        index = int(time.time() / self.interval) % len(rows)
        row = dict(rows[index])
        previous = rows[index - 1]["price"] if index else rows[0]["open"]
        row.update({
            "symbol": symbol,
            "change": row["price"] - previous,
            "change_pct": (row["price"] / previous - 1) * 100 if previous else 0,
            "replay_index": index,
            "replay_total": len(rows),
        })
        return row
