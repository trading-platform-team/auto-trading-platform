"""금융위원회 주식시세정보 API 클라이언트.

공공데이터포털 서비스키 하나로 종목별 과거 일봉을 조회한다.
"""

from datetime import date, timedelta
from urllib.parse import unquote

import httpx


class PublicDataError(RuntimeError):
    pass


class PublicStockClient:
    def __init__(self, service_key: str, base_url: str, transport: httpx.AsyncBaseTransport | None = None):
        self.service_key = unquote(service_key.strip())
        self.client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=15, transport=transport)

    @property
    def enabled(self) -> bool:
        return bool(self.service_key)

    async def close(self) -> None:
        await self.client.aclose()

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
