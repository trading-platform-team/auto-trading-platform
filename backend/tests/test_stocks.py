"""종목 목록·현재가·일봉 서비스 + 가상계좌 연습 API (가짜 키움 서버로 시험)"""

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.kiwoom.client import KiwoomClient, KiwoomError, num
from app.main import app
from app.market.cache import save_tick
from app.market.sources import make_tick
from app.stocks.service import QuoteUnavailable, StockService, market_open
from tests.conftest import login

KOSPI = [
    {
        "code": "005930",
        "name": "삼성전자",
        "listCount": "0000005919637922",
        "lastPrice": "00192500",
        "marketName": "거래소",
        "upName": "전기·전자",
        "orderWarning": "0",
    },
    {
        "code": "006400",
        "name": "삼성SDI",
        "listCount": "0000000068764530",
        "lastPrice": "00250000",
        "upName": "전기·전자",
        "orderWarning": "0",
    },
    {
        "code": "005380",
        "name": "현대차",
        "listCount": "0000000209416191",
        "lastPrice": "00240000",
        "upName": "운송장비·부품",
        "orderWarning": "3",
    },
    {
        "code": "069500",
        "name": "KODEX 200",
        "listCount": "0000000100000000",
        "lastPrice": "00040000",
        "upName": "",
        "orderWarning": "1",
    },
]
KOSPI_PAGE2 = [
    {
        "code": "000660",
        "name": "SK하이닉스",
        "listCount": "0000000728002365",
        "lastPrice": "00500000",
        "upName": "전기·전자",
        "orderWarning": "0",
    }
]
KOSDAQ = [
    {
        "code": "247540",
        "name": "에코프로비엠",
        "listCount": "0000000097801344",
        "lastPrice": "00150000",
        "upName": "일반전기전자",
        "orderWarning": "0",
    }
]
QUOTES = {
    "005930": {"cur_prc": "-192500", "pred_pre": "-2500", "flu_rt": "-1.28", "trde_qty": "8725621"},
    "000660": {"cur_prc": "+510000", "pred_pre": "+10000", "flu_rt": "+2.00", "trde_qty": "2000000"},
    "006400": {"cur_prc": "250000", "pred_pre": "0", "flu_rt": "0.00", "trde_qty": "100"},
    "005380": {"cur_prc": "+246000", "pred_pre": "+6000", "flu_rt": "+2.50", "trde_qty": "500000"},
    "247540": {"cur_prc": "-150000", "pred_pre": "-3000", "flu_rt": "-1.96", "trde_qty": "300000"},
}


class FakeKiwoom:
    def __init__(self):
        self.calls: list[str] = []
        self.tokens = 0
        self.expire_next = False
        self.fail = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        if request.url.path == "/oauth2/token":
            self.tokens += 1
            return httpx.Response(
                200, json={"return_code": 0, "token": f"T{self.tokens}", "expires_dt": "29991231235959"}
            )
        api_id = request.headers["api-id"]
        self.calls.append(api_id)
        if self.fail:
            return httpx.Response(200, json={"return_code": 8010, "return_msg": "IP 불일치"})
        if self.expire_next:
            self.expire_next = False
            return httpx.Response(200, json={"return_code": 8005, "return_msg": "토큰 만료"})
        if api_id == "ka10099":
            tp = body["mrkt_tp"]
            if tp == "0" and request.headers.get("next-key") == "P2":
                return httpx.Response(200, json={"return_code": 0, "list": KOSPI_PAGE2})
            if tp == "0":
                return httpx.Response(
                    200, json={"return_code": 0, "list": KOSPI}, headers={"cont-yn": "Y", "next-key": "P2"}
                )
            if tp == "10":
                return httpx.Response(200, json={"return_code": 0, "list": KOSDAQ})
            if tp == "8":
                return httpx.Response(200, json={"return_code": 0, "list": [{"code": "069500", "name": "KODEX 200"}]})
            return httpx.Response(200, json={"return_code": 0, "list": []})
        if api_id == "ka10095":
            rows = [{"stk_cd": c, "stk_nm": "", **QUOTES[c]} for c in body["stk_cd"].split("|") if c in QUOTES]
            return httpx.Response(200, json={"return_code": 0, "atn_stk_infr": rows})
        if api_id == "ka10081":
            rows = [
                {
                    "dt": f"202611{d:02d}",
                    "open_pric": "190000",
                    "high_pric": "+195000",
                    "low_pric": "-189000",
                    "cur_prc": "+192500",
                    "trde_qty": "1000",
                }
                for d in (17, 16, 13)
            ]
            return httpx.Response(200, json={"return_code": 0, "stk_dt_pole_chart_qry": rows})
        return httpx.Response(404)


def make_service(fake_redis, fake: FakeKiwoom) -> StockService:
    client = KiwoomClient(
        "https://mockapi.kiwoom.com", "key", "secret", transport=httpx.MockTransport(fake), min_interval=0
    )
    return StockService(fake_redis, client)


def test_num_parses_signed_strings():
    assert num("-192500") == 192500 and num("-1.28", signed=True) == -1.28
    assert num("00250000") == 250000 and num("") == 0 and num("+") == 0 and num("1,234") == 1234


def test_market_open():
    from datetime import datetime

    from app.kiwoom.client import KST

    assert market_open(datetime(2026, 11, 17, 10, 0, tzinfo=KST))
    assert not market_open(datetime(2026, 11, 17, 15, 30, tzinfo=KST))
    assert not market_open(datetime(2026, 11, 15, 10, 0, tzinfo=KST))  # 일요일


def test_master_search_browse_quotes(fake_redis):
    fake = FakeKiwoom()
    svc = make_service(fake_redis, fake)

    async def run():
        master = await svc.master()
        assert set(master) == {"005930", "006400", "005380", "000660", "247540"}  # 연속조회 2페이지, ETF 제외
        assert master["005380"]["warning"] == "단기과열"
        assert svc.status()["source"] == "kiwoom"

        found = await svc.search("삼성")
        assert [x["symbol"] for x in found] == ["005930", "006400"]  # 시가총액 큰 순
        assert found[0]["price"] == 192500 and found[0]["change_pct"] == -1.28
        assert (await svc.search("000660"))[0]["name"] == "SK하이닉스"

        sectors = await svc.sectors("KOSPI")
        assert sectors[0] == {"sector": "전기·전자", "count": 3}
        cap = await svc.browse("KOSPI", "전기·전자", "cap", 30)
        assert [x["symbol"] for x in cap] == ["005930", "000660", "006400"]
        up = await svc.browse("KOSPI", None, "change", 30)
        assert up[0]["symbol"] == "005380"
        assert (await svc.browse("KOSDAQ", None, "fall", 30))[0]["symbol"] == "247540"

        n = fake.calls.count("ka10095")
        await svc.quotes(["005930"])  # 5초 캐시
        assert fake.calls.count("ka10095") == n

        bars = await svc.daily("005930")
        assert [b["date"] for b in bars] == ["2026-11-13", "2026-11-16", "2026-11-17"]
        assert bars[-1]["close"] == 192500 and bars[-1]["low"] == 189000

    asyncio.run(run())


def test_master_loaded_once_for_concurrent_requests(fake_redis):
    fake = FakeKiwoom()
    svc = make_service(fake_redis, fake)

    async def run():
        results = await asyncio.gather(*(svc.master() for _ in range(10)))
        assert all(len(r) == 5 for r in results)
        assert fake.calls.count("ka10099") == 4  # ETF 1 + 코스피 2페이지 + 코스닥 1, 요청 10개여도 한 번만
        fresh = make_service(fake_redis, fake)  # 서버 재시작: Redis 캐시 사용
        await fresh.master()
        assert fake.calls.count("ka10099") == 4 and fresh.status()["source"] == "kiwoom"

    asyncio.run(run())


def test_token_reissued_when_expired(fake_redis):
    fake = FakeKiwoom()
    svc = make_service(fake_redis, fake)

    async def run():
        await svc.master()
        fake.expire_next = True
        assert await svc.price("000660") == 510000
        assert fake.tokens == 2

    asyncio.run(run())


def test_fallback_to_mock_when_kiwoom_fails(fake_redis):
    fake = FakeKiwoom()
    fake.fail = True
    svc = make_service(fake_redis, fake)

    async def run():
        await save_tick(fake_redis, make_tick("005930", "삼성전자", 70000, 100, 500, 500))
        master = await svc.master()
        assert len(master) == 5 and svc.status()["source"] == "mock"
        assert "IP 불일치" in svc.status()["error"]
        assert await svc.price("005930") == 70000
        n = len(fake.calls)
        await svc.master()  # 실패 직후에는 매번 다시 호출하지 않음
        assert len(fake.calls) == n

    asyncio.run(run())


def test_network_error_becomes_kiwoom_error(fake_redis):
    def down(request):
        raise httpx.ConnectError("연결 거부")

    client = KiwoomClient("https://x", "k", "s", transport=httpx.MockTransport(down), min_interval=0)
    svc = StockService(fake_redis, client)

    async def run():
        assert len(await svc.master()) == 5  # 가상 종목으로 대체
        assert "연결할 수 없어요" in svc.status()["error"]
        with pytest.raises(QuoteUnavailable):  # 키는 있는데 연결 실패 → 이유와 함께 실패
            await svc.daily("005930")

    asyncio.run(run())


def test_client_raises_error_code():
    fake = FakeKiwoom()
    fake.fail = True
    client = KiwoomClient("https://x", "k", "s", transport=httpx.MockTransport(fake), min_interval=0)
    with pytest.raises(KiwoomError) as e:
        asyncio.run(client.call("ka10095", "/api/dostk/stkinfo", {"stk_cd": "005930"}))
    assert e.value.code == "8010"


# ---------- API ----------
@pytest.fixture
def client(sqlite_db, fake_redis, monkeypatch):
    monkeypatch.setattr("app.main.settings.enable_consumer", False)
    monkeypatch.setattr("app.main.aioredis.from_url", lambda *a, **k: fake_redis)
    fake = FakeKiwoom()
    real_init = KiwoomClient.__init__

    def init(self, base_url, app_key, secret_key, **kw):
        real_init(self, base_url, "key", "secret", transport=httpx.MockTransport(fake), min_interval=0)

    monkeypatch.setattr(KiwoomClient, "__init__", init)
    with TestClient(app) as c:
        yield c


def test_stocks_api_and_practice_with_real_prices(client):
    assert client.get("/stocks/status").json()["source"] == "kiwoom"
    assert client.get("/stocks/markets").json()[1] == {"market": "KOSDAQ", "label": "코스닥", "count": 1}
    assert client.get("/stocks/search", params={"q": "하이닉스"}).json()[0]["price"] == 510000
    assert client.get("/stocks/browse", params={"market": "KOSPI", "sort": "volume"}).json()[0]["symbol"] == "005930"
    assert client.get("/stocks/999999").status_code == 404
    assert client.get("/stocks/005930").json()["sector"] == "전기·전자"
    assert len(client.get("/stocks/005930/daily").json()) == 3

    login(client)
    res = client.post("/edu/account/orders", json={"symbol": "247540", "side": "buy", "quantity": 10}).json()
    assert res["price"] == 150000  # 키움 현재가로 체결 (가상 시세에 없는 코스닥 종목)
    pos = res["account"]["positions"][0]
    assert pos["name"] == "에코프로비엠" and pos["quantity"] == 10
    assert (
        client.post("/edu/account/orders", json={"symbol": "999999", "side": "buy", "quantity": 1}).status_code == 404
    )

    assert client.get("/edu/watchlist").json() == []
    assert [x["symbol"] for x in client.put("/edu/watchlist/000660").json()] == ["000660"]
    items = client.put("/edu/watchlist/005930").json()
    assert [x["symbol"] for x in items] == ["000660", "005930"] and items[0]["price"] == 510000
    assert client.put("/edu/watchlist/999999").status_code == 404
    assert [x["symbol"] for x in client.delete("/edu/watchlist/000660").json()] == ["005930"]
