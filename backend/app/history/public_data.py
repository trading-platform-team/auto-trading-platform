"""금융위원회 주식시세정보 API 클라이언트.

공공데이터포털 서비스키 하나로 종목별 과거 일봉을 조회한다.
"""

import time
from datetime import date, timedelta
from urllib.parse import unquote

import httpx


class PublicDataError(RuntimeError):
    pass


class PublicStockClient:
    def __init__(self, service_key: str, base_url: str, transport: httpx.AsyncBaseTransport | None = None):
        self.service_key = unquote(service_key.strip())
        self.client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=15, transport=transport)
        self._latest_cache: dict[str, tuple[float, dict]] = {}
        self._master_cache: tuple[float, list[dict]] | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.service_key)

    async def close(self) -> None:
        await self.client.aclose()

    async def master(self) -> list[dict]:
        """최신 거래일의 코스피·코스닥 종목 목록을 시세 API에서 만든다."""
        if not self.enabled:
            return []
        if self._master_cache and self._master_cache[0] > time.monotonic():
            return [dict(row) for row in self._master_cache[1]]

        async def fetch(params: dict) -> dict:
            try:
                response = await self.client.get(
                    "/getStockPriceInfo_V2",
                    params={"serviceKey": self.service_key, "resultType": "json", **params},
                )
                response.raise_for_status()
                payload = response.json().get("response", {})
            except (httpx.HTTPError, ValueError) as exc:
                raise PublicDataError(f"공공데이터 종목 목록 호출 실패: {exc}") from exc
            header = payload.get("header") or {}
            if str(header.get("resultCode", "00")) not in {"00", "0"}:
                raise PublicDataError(str(header.get("resultMsg") or "공공데이터 응답 오류"))
            return payload.get("body") or {}

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

        rows: dict[str, dict] = {}
        page = 1
        while page <= 20:
            try:
                response = await self.client.get(
                    "/getStockPriceInfo_V2",
                    params={
                        "serviceKey": self.service_key,
                        "resultType": "json",
                        "pageNo": page,
                        "numOfRows": 1000,
                        "beginBasDt": start.strftime("%Y%m%d"),
                        # 공공데이터 명세상 endBasDt는 기준일자 미만이므로 선택 종료일의 다음 날을 보낸다.
                        "endBasDt": (end + timedelta(days=1)).strftime("%Y%m%d"),
                        "likeSrtnCd": symbol,
                    },
                )
                response.raise_for_status()
                payload = response.json().get("response", {})
            except (httpx.HTTPError, ValueError) as exc:
                raise PublicDataError(f"공공데이터 주식시세 호출 실패: {exc}") from exc

            header = payload.get("header") or {}
            if str(header.get("resultCode", "00")) not in {"00", "0"}:
                raise PublicDataError(str(header.get("resultMsg") or "공공데이터 응답 오류"))
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
        return [rows[key] for key in sorted(rows)]

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
