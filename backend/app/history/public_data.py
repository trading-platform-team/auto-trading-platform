"""금융위원회 주식시세정보 API 클라이언트.

공공데이터포털 서비스키 하나로 종목별 과거 일봉을 조회한다.

- 서비스키가 URL 쿼리에 들어가므로 오류 메시지에는 URL을 절대 넣지 않는다 (화면에 그대로 보인다)
- 초당 요청 제한이 있어서 호출 사이를 MIN_INTERVAL초씩 띄우고, 429(요청 과다)를 받으면 COOLDOWN초 동안 멈춘다
- 일봉은 DAILY_TTL초 동안 보관한다 (종목 목록 30개를 그릴 때마다 다시 부르지 않게)
"""

import asyncio
import time
from datetime import date, timedelta
from urllib.parse import unquote

import httpx

MIN_INTERVAL = 0.35  # 초당 3번 이하
COOLDOWN = 60.0
DAILY_TTL = 600.0


class PublicDataError(RuntimeError):
    pass


def describe(exc: Exception) -> str:
    """사용자에게 보여도 되는 오류 설명 (요청 URL·서비스키 없이)"""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 429:
            return "요청이 너무 많아 잠시 막혔어요"
        return f"HTTP {code}"
    if isinstance(exc, httpx.TimeoutException):
        return "응답 시간 초과"
    if isinstance(exc, httpx.HTTPError):
        return "연결 실패"
    return "응답 형식 오류"


def _day_quote(raw: dict, day: str) -> dict | None:
    """getStockPriceInfo 한 줄 → 그날 종가 시세 (목록 표시용)"""
    try:
        price = float(raw.get("clpr") or 0)
        if price <= 0:
            return None
        return {
            "price": price,
            "change": float(raw.get("vs") or 0),
            "change_pct": float(raw.get("fltRt") or 0),
            "volume": int(float(raw.get("trqu") or 0)),
            "open": float(raw.get("mkp") or 0),
            "high": float(raw.get("hipr") or 0),
            "low": float(raw.get("lopr") or 0),
            "price_date": f"{day[:4]}-{day[4:6]}-{day[6:]}",
            "source": "public_data",
        }
    except (TypeError, ValueError):
        return None


class PublicStockClient:
    def __init__(self, service_key: str, base_url: str, transport: httpx.AsyncBaseTransport | None = None):
        self.service_key = unquote(service_key.strip())
        self.client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=15, transport=transport)
        self._latest_cache: dict[str, tuple[float, dict]] = {}
        self._master_cache: tuple[float, list[dict]] | None = None
        self._daily_cache: dict[tuple, tuple[float, list[dict]]] = {}
        self._limit = asyncio.Lock()  # 한 번에 하나씩, MIN_INTERVAL 간격으로
        self._last_call = 0.0
        self._blocked_until = 0.0  # 429를 받은 뒤 다시 부를 수 있는 시각

    @property
    def enabled(self) -> bool:
        return bool(self.service_key)

    async def close(self) -> None:
        await self.client.aclose()

    async def _get(self, params: dict, what: str) -> dict:
        """getStockPriceInfo_V2 호출 → response 본문(header·body). 실패하면 URL 없는 PublicDataError"""
        if time.monotonic() < self._blocked_until:
            raise PublicDataError(f"공공데이터 {what} 실패: 요청이 너무 많아 잠시 쉬는 중이에요")
        async with self._limit:
            wait = self._last_call + MIN_INTERVAL - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            if time.monotonic() < self._blocked_until:  # 기다리는 사이 다른 요청이 429를 받았으면
                raise PublicDataError(f"공공데이터 {what} 실패: 요청이 너무 많아 잠시 쉬는 중이에요")
            self._last_call = time.monotonic()
            try:
                response = await self.client.get(
                    "/getStockPriceInfo_V2",
                    params={"serviceKey": self.service_key, "resultType": "json", **params},
                )
                response.raise_for_status()
                payload = response.json().get("response", {})
            except (httpx.HTTPError, ValueError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                    self._blocked_until = time.monotonic() + COOLDOWN
                raise PublicDataError(f"공공데이터 {what} 실패: {describe(exc)}") from None
        header = payload.get("header") or {}
        if str(header.get("resultCode", "00")) not in {"00", "0"}:
            raise PublicDataError(str(header.get("resultMsg") or "공공데이터 응답 오류"))
        return payload

    async def master(self) -> list[dict]:
        """최신 거래일의 코스피·코스닥 종목 목록을 시세 API에서 만든다."""
        if not self.enabled:
            return []
        if self._master_cache and self._master_cache[0] > time.monotonic():
            return [dict(row) for row in self._master_cache[1]]

        async def fetch(params: dict) -> dict:
            return (await self._get(params, "종목 목록 호출")).get("body") or {}

        first = await fetch({"pageNo": 1, "numOfRows": 1})
        item = ((first.get("items") or {}).get("item") or [])
        if isinstance(item, dict):
            item = [item]
        latest_day = str(item[0].get("basDt", "")) if item else ""
        if len(latest_day) != 8:
            raise PublicDataError("최신 거래일을 확인하지 못했습니다")

        rows: list[dict] = []
        page = 1
        while page <= 10:
            body = await fetch({"pageNo": page, "numOfRows": 1000, "basDt": latest_day})
            items = (body.get("items") or {}).get("item") or []
            if isinstance(items, dict):
                items = [items]
            for raw in items:
                market = str(raw.get("mrktCtg") or "").upper()
                code = str(raw.get("srtnCd") or "").strip()
                name = str(raw.get("itmsNm") or "").strip()
                if market not in {"KOSPI", "KOSDAQ"} or len(code) != 6 or not name:
                    continue
                try:
                    cap = float(raw.get("mrktTotAmt") or 0)
                except (TypeError, ValueError):
                    cap = 0
                rows.append({
                    "code": code, "name": name, "market": market, "sector": "기타",
                    "cap": cap, "warning": None,
                    "quote": _day_quote(raw, latest_day),  # 같은 응답의 종가: 목록 가격을 따로 부르지 않게
                })
            total = int(body.get("totalCount") or 0)
            if page * 1000 >= total or not items:
                break
            page += 1
        if not rows:
            raise PublicDataError("공공데이터 종목 목록이 비어 있습니다")
        unique = list({row["code"]: row for row in rows}.values())
        self._master_cache = (time.monotonic() + 12 * 3600, unique)
        return [dict(row) for row in unique]

    async def daily(self, symbol: str, start: date, end: date) -> list[dict]:
        if not self.enabled or start > end:
            return []
        key = (symbol, start, end)
        cached = self._daily_cache.get(key)
        if cached and cached[0] > time.monotonic():
            return [dict(row) for row in cached[1]]

        rows: dict[str, dict] = {}
        page = 1
        while page <= 20:
            payload = await self._get(
                {
                    "pageNo": page,
                    "numOfRows": 1000,
                    "beginBasDt": start.strftime("%Y%m%d"),
                    # 공공데이터 명세상 endBasDt는 기준일자 미만이므로 선택 종료일의 다음 날을 보낸다.
                    "endBasDt": (end + timedelta(days=1)).strftime("%Y%m%d"),
                    "likeSrtnCd": symbol,
                },
                "주식시세 호출",
            )
            body = payload.get("body") or {}
            raw_items = (body.get("items") or {}).get("item") or []
            if isinstance(raw_items, dict):
                raw_items = [raw_items]
            for raw in raw_items:
                if str(raw.get("srtnCd", "")).strip() != symbol:
                    continue
                dt = str(raw.get("basDt", ""))
                if len(dt) != 8:
                    continue
                try:
                    rows[dt] = {
                        "date": f"{dt[:4]}-{dt[4:6]}-{dt[6:]}",
                        "open": float(raw.get("mkp") or 0),
                        "high": float(raw.get("hipr") or 0),
                        "low": float(raw.get("lopr") or 0),
                        "close": float(raw.get("clpr") or 0),
                        "volume": int(float(raw.get("trqu") or 0)),
                    }
                except (TypeError, ValueError):
                    continue

            total = int(body.get("totalCount") or 0)
            if page * 1000 >= total or not raw_items:
                break
            page += 1
        result = [rows[d] for d in sorted(rows)]
        self._daily_cache[key] = (time.monotonic() + DAILY_TTL, result)
        return [dict(row) for row in result]

    async def latest(self, symbol: str, end: date | None = None) -> dict | None:
        """최근 실제 거래일 종가. 가상계좌의 반복 조회를 줄이기 위해 10분간 보관한다."""
        end = end or date.today()
        cache_key = f"{symbol}:{end.isoformat()}"
        cached = self._latest_cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return dict(cached[1])
        bars = await self.daily(symbol, end - timedelta(days=30), end)
        if not bars:
            return None
        bar = bars[-1]
        previous = bars[-2]["close"] if len(bars) > 1 else None
        change = bar["close"] - previous if previous else None
        quote = {
            "symbol": symbol,
            "price": bar["close"],
            "open": bar["open"],
            "high": bar["high"],
            "low": bar["low"],
            "volume": bar["volume"],
            "change": change,
            "change_pct": change / previous * 100 if previous else None,
            "price_date": bar["date"],
            "source": "public_data",
        }
        self._latest_cache[cache_key] = (time.monotonic() + 600, quote)
        return dict(quote)
