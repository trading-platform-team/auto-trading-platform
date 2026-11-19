"""종목 목록·현재가·일봉 서비스 (가상계좌 연습용)

키움 키가 있으면:
- 종목 목록: ka10099 (코스피 0, 코스닥 10). ETF·ETN(8, 60)은 빼고, 하루 한 번 받아 Redis에 보관
- 현재가: ka10095 관심종목정보요청 (종목코드를 | 로 이어 여러 종목을 한 번에). 5초 캐시
- 일봉: ka10081 주식일봉차트조회. 10분 캐시

키가 없거나 키움 호출이 실패하면 가상 시세(collector가 만든 Redis price:latest)로 대체한다.
"""

import asyncio
import json
import logging
import time
from datetime import datetime

from app.history.public_data import PublicDataError, PublicStockClient
from app.kiwoom.client import KST, KiwoomClient, KiwoomError, num
from app.market.cache import get_latest
from app.market.sources import DEFAULT_SYMBOLS

log = logging.getLogger("uvicorn.error")

MASTER_KEY = "stocks:master"
PUBLIC_MASTER_KEY = "stocks:master:public:v2"  # v2: 종목마다 최근 종가(quote) 포함
MASTER_TTL = 12 * 3600
QUOTE_KEY = "stocks:quote:{code}"
QUOTE_TTL = 5
DAILY_KEY = "stocks:daily:{code}"
DAILY_TTL = 600
RETRY_SEC = 60
MASTER_WAIT = 5  # 요청이 종목 목록을 기다리는 최대 시간(초)
BATCH = 20  # ka10095 한 번에 요청할 종목 수

MARKETS = {"KOSPI": "0", "KOSDAQ": "10"}
MARKET_LABEL = {"KOSPI": "코스피", "KOSDAQ": "코스닥"}
EXCLUDE_MARKETS = ("8",)  # ETF
WARNINGS = {"2": "정리매매", "3": "단기과열", "4": "투자위험", "5": "투자경고"}

# 키움 연결 전·실패 시 쓰는 가상 시세 종목
FALLBACK = {
    "005930": ("KOSPI", "전기·전자"),
    "000660": ("KOSPI", "전기·전자"),
    "035420": ("KOSPI", "서비스업"),
    "005380": ("KOSPI", "운송장비·부품"),
    "035720": ("KOSPI", "서비스업"),
}


class StockNotFound(KeyError):
    pass


class QuoteUnavailable(RuntimeError):
    pass


def market_open(now: datetime | None = None) -> bool:
    """정규장(평일 09:00~15:30, KST) 여부. 공휴일은 따지지 않는다"""
    now = (now or datetime.now(KST)).astimezone(KST)
    hm = now.hour * 100 + now.minute
    return now.weekday() < 5 and 900 <= hm < 1530


def _master_row(row: dict, market: str) -> dict | None:
    code = str(row.get("code", "")).strip()
    name = str(row.get("name", "")).strip()
    if len(code) != 6 or not name:
        return None
    price = num(row.get("lastPrice"))
    shares = num(row.get("listCount"))
    return {
        "code": code,
        "name": name,
        "market": market,
        "sector": str(row.get("upName") or "").strip() or "기타",
        "cap": price * shares,  # 시가총액 근삿값 (정렬용)
        "warning": WARNINGS.get(str(row.get("orderWarning", "")).strip()),
    }


def _quote_row(row: dict) -> dict:
    return {
        "symbol": str(row.get("stk_cd", "")).strip().split("_")[0],
        "price": num(row.get("cur_prc")),
        "change": num(row.get("pred_pre"), signed=True),
        "change_pct": num(row.get("flu_rt"), signed=True),
        "volume": int(num(row.get("trde_qty"))),
        "open": num(row.get("open_pric")),
        "high": num(row.get("high_pric")),
        "low": num(row.get("low_pric")),
        "upper_limit": num(row.get("upl_pric")),
        "lower_limit": num(row.get("lst_pric")),
    }


class StockService:
    def __init__(self, redis, kiwoom: KiwoomClient | None = None, public: PublicStockClient | None = None):
        self.redis = redis
        self.kiwoom = kiwoom if kiwoom and kiwoom.enabled else None
        self.public = public if public and public.enabled else None
        self._master: dict[str, dict] = {}
        self._real = False
        self._source = "mock"
        self._loading: asyncio.Task | None = None
        self._retry_at = 0.0  # 키움 종목 목록 실패 후 다시 시도할 시각 (매 요청마다 재시도하지 않도록)
        self.last_error: str | None = None

    # ---------- 상태 ----------
    @property
    def source(self) -> str:
        return self._source if self._real else "mock"

    def status(self) -> dict:
        return {
            "source": self.source,
            "kiwoom_key": self.kiwoom is not None,
            "stocks": len(self._master),
            "loading": self._loading is not None,
            "market_open": market_open(),
            "error": self.last_error,
        }

    # ---------- 종목 목록 ----------
    def warm(self) -> None:
        """서버 시작 시 종목 목록을 미리 받기 시작 (기다리지 않음)"""
        if (self.public or self.kiwoom) and not self._real and self._loading is None:
            self._loading = asyncio.create_task(self._fetch_master())

    async def master(self) -> dict[str, dict]:
        """종목 목록. 키움 목록을 받는 중이면 최대 MASTER_WAIT초만 기다리고, 그동안은 가상 종목으로 응답

        목록 받기는 한 번에 하나만 실행된다 (요청마다 새로 받지 않음).
        """
        if self._real:
            return self._master
        if (self.public or self.kiwoom) and time.monotonic() >= self._retry_at:
            self.warm()
            if self._loading is not None:
                try:
                    await asyncio.wait_for(asyncio.shield(self._loading), timeout=MASTER_WAIT)
                except TimeoutError:
                    pass  # 계속 받는 중 → 이번 요청은 가상 종목
            if self._real:
                return self._master
        if not self._master:
            self._master = {
                code: {
                    "code": code,
                    "name": name,
                    "market": FALLBACK[code][0],
                    "sector": FALLBACK[code][1],
                    "cap": float(price),
                    "warning": None,
                }
                for code, (name, price) in DEFAULT_SYMBOLS.items()
            }
        return self._master

    async def _fetch_master(self) -> None:
        started = time.monotonic()
        try:
            cache_key = PUBLIC_MASTER_KEY if self.public else MASTER_KEY
            cached = await self.redis.get(cache_key)
            rows = json.loads(cached) if cached else (
                await self.public.master() if self.public else await self._load_master()
            )
            if not cached:
                await self.redis.set(cache_key, json.dumps(rows, ensure_ascii=False), ex=MASTER_TTL)
            self._master = {r["code"]: r for r in rows}
            self._real = True
            self._source = "public_data" if self.public else "kiwoom"
            self.last_error = None
            log.info(
                "종목 목록 %d개 (%.1f초, %s)", len(rows), time.monotonic() - started,
                "캐시" if cached else self._source,
            )
        except (KiwoomError, PublicDataError, OSError, ValueError) as e:
            self.last_error = f"종목 목록: {e}"
            self._retry_at = time.monotonic() + RETRY_SEC
            log.warning("종목 목록 실패, 가상 종목으로 대체: %s", e)
        finally:
            self._loading = None

    async def _list_market(self, mrkt_tp: str) -> list[dict]:
        rows, cont, pages = [], "", 0
        for _ in range(30):  # 연속조회 (안전장치)
            data, head = await self.kiwoom.call("ka10099", "/api/dostk/stkinfo", {"mrkt_tp": mrkt_tp}, cont)
            rows.extend(data.get("list") or [])
            pages += 1
            if head["cont-yn"] != "Y" or not head["next-key"]:
                break
            cont = head["next-key"]
        log.info("ka10099 mrkt_tp=%s: %d개, %d페이지", mrkt_tp, len(rows), pages)
        return rows

    async def _load_master(self) -> list[dict]:
        exclude: set[str] = set()
        for tp in EXCLUDE_MARKETS:
            try:
                exclude |= {str(r.get("code", "")).strip() for r in await self._list_market(tp)}
            except KiwoomError:
                pass  # ETF 목록을 못 받아도 주식 목록은 계속
        result = []
        for market, tp in MARKETS.items():
            for raw in await self._list_market(tp):
                row = _master_row(raw, market)
                if row and row["code"] not in exclude:
                    result.append(row)
        if not result:
            raise KiwoomError("종목 목록이 비어 있어요")
        return result

    async def info(self, code: str) -> dict:
        row = (await self.master()).get(code)
        if not row:
            raise StockNotFound(code)
        return row

    async def sectors(self, market: str) -> list[dict]:
        counts: dict[str, int] = {}
        for r in (await self.master()).values():
            if r["market"] == market:
                counts[r["sector"]] = counts.get(r["sector"], 0) + 1
        return [{"sector": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]

    async def search(self, q: str, limit: int = 20) -> list[dict]:
        key = q.replace(" ", "").lower()
        if not key:
            return []
        ranked = []
        for r in (await self.master()).values():
            name = r["name"].replace(" ", "").lower()
            if r["code"] == key or name == key:
                rank = 0
            elif name.startswith(key) or r["code"].startswith(key):
                rank = 1
            elif key in name:
                rank = 2
            else:
                continue
            ranked.append((rank, -r["cap"], r))
        ranked.sort(key=lambda x: (x[0], x[1]))
        return await self.with_quotes([r for _, _, r in ranked[:limit]])

    async def browse(self, market: str, sector: str | None, sort: str, limit: int) -> list[dict]:
        """시장·업종으로 거른 뒤 시가총액 상위 limit개의 현재가를 받아 정렬"""
        rows = [
            r for r in (await self.master()).values() if r["market"] == market and (not sector or r["sector"] == sector)
        ]
        rows.sort(key=lambda r: -r["cap"])
        items = await self.with_quotes(rows[:limit])
        keys = {
            "change": lambda x: -(x.get("change_pct") or 0),
            "fall": lambda x: x.get("change_pct") or 0,
            "volume": lambda x: -(x.get("volume") or 0),
        }
        if sort in keys:
            items.sort(key=keys[sort])
        return items

    # ---------- 현재가 ----------
    async def quotes(self, codes: list[str]) -> dict[str, dict]:
        """종목코드 목록 → {코드: 시세}. 시세를 못 구한 종목은 빠진다"""
        codes = list(dict.fromkeys(c for c in codes if c))
        if not codes:
            return {}
        master = await self.master()
        out: dict[str, dict] = {}
        if self.kiwoom and self._real:
            cached = await self.redis.mget([QUOTE_KEY.format(code=c) for c in codes])
            missing = []
            for c, raw in zip(codes, cached, strict=True):
                if raw:
                    out[c] = json.loads(raw)
                else:
                    missing.append(c)
            for i in range(0, len(missing), BATCH):
                chunk = missing[i : i + BATCH]
                try:
                    data, _ = await self.kiwoom.call("ka10095", "/api/dostk/stkinfo", {"stk_cd": "|".join(chunk)})
                except (KiwoomError, OSError) as e:
                    self.last_error = f"현재가: {e}"
                    log.warning("키움 현재가 실패: %s", e)
                    break
                pipe = self.redis.pipeline()
                for raw in data.get("atn_stk_infr") or []:
                    q = _quote_row(raw)
                    if q["symbol"] in master and q["price"] > 0:
                        q["source"] = "kiwoom"
                        out[q["symbol"]] = q
                        pipe.set(QUOTE_KEY.format(code=q["symbol"]), json.dumps(q), ex=QUOTE_TTL)
                await pipe.execute()
        # 가상 시세로 채울 수 있는 종목은 채운다 (키 없음 / 키움 실패)
        lacking = [c for c in codes if c not in out]
        if lacking:
            mock = {t["symbol"]: t for t in await get_latest(self.redis)}
            for c in lacking:
                if c in mock:
                    t = mock[c]
                    change = change_pct = None
                    day = (master.get(c) or {}).get("quote")
                    if day and day.get("change") is not None and t.get("source") != "mock":
                        prev = day["price"] - day["change"]  # 전일 종가 기준 등락 (재생 가격)
                        if prev > 0:
                            change = t["price"] - prev
                            change_pct = round(change / prev * 100, 2)
                    out[c] = {
                        "symbol": c,
                        "price": t["price"],
                        "change": change,
                        "change_pct": change_pct,
                        "volume": t.get("volume"),
                        "source": t.get("source", "mock"),
                    }
        # 공공데이터 종목 목록에 같이 받아 둔 최근 종가 (추가 호출 없음)
        for c in codes:
            if c not in out and (master.get(c) or {}).get("quote"):
                out[c] = {"symbol": c, **master[c]["quote"]}
        for c, q in out.items():
            meta = master.get(c, {})
            q.update(
                name=meta.get("name", c),
                market=meta.get("market"),
                sector=meta.get("sector"),
                warning=meta.get("warning"),
            )
        return out

    async def price(self, code: str) -> float:
        await self.info(code)
        q = (await self.quotes([code])).get(code)
        if not q or not q["price"]:
            raise QuoteUnavailable(code)
        return q["price"]

    async def with_quotes(self, rows: list[dict]) -> list[dict]:
        quotes = await self.quotes([r["code"] for r in rows])
        result = []
        for r in rows:
            q = quotes.get(r["code"], {})
            result.append(
                {
                    "symbol": r["code"],
                    "name": r["name"],
                    "market": r["market"],
                    "sector": r["sector"],
                    "warning": r["warning"],
                    "price": q.get("price"),
                    "change": q.get("change"),
                    "change_pct": q.get("change_pct"),
                    "volume": q.get("volume"),
                }
            )
        return result

    # ---------- 일봉 ----------
    async def daily(self, code: str, limit: int = 120) -> list[dict]:
        """일봉. 키움 키가 없으면 빈 목록, 키움 목록을 받는 중이거나 호출이 실패하면 QuoteUnavailable(이유)"""
        await self.info(code)
        if not self.kiwoom:
            return []
        if not self._real:
            raise QuoteUnavailable("키움 종목 목록을 받는 중이에요")
        key = DAILY_KEY.format(code=code)
        cached = await self.redis.get(key)
        if cached:
            bars = json.loads(cached)
        else:
            try:
                data, _ = await self.kiwoom.call(
                    "ka10081",
                    "/api/dostk/chart",
                    {"stk_cd": code, "base_dt": datetime.now(KST).strftime("%Y%m%d"), "upd_stkpc_tp": "1"},
                )
            except (KiwoomError, OSError) as e:
                log.warning("키움 일봉 실패 %s: %s", code, e)
                raise QuoteUnavailable(str(e)) from e
            bars = []
            for r in data.get("stk_dt_pole_chart_qry") or []:
                dt = str(r.get("dt", ""))
                if len(dt) != 8:
                    continue
                bars.append(
                    {
                        "date": f"{dt[:4]}-{dt[4:6]}-{dt[6:]}",
                        "open": num(r.get("open_pric")),
                        "high": num(r.get("high_pric")),
                        "low": num(r.get("low_pric")),
                        "close": num(r.get("cur_prc")),
                        "volume": int(num(r.get("trde_qty"))),
                    }
                )
            bars.sort(key=lambda b: b["date"])
            await self.redis.set(key, json.dumps(bars), ex=DAILY_TTL)
        return bars[-limit:]
