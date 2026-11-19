import asyncio
import json
from datetime import date

import httpx

from app.history.public_data import PublicStockClient
from app.stocks.service import StockService


def test_public_stock_master_uses_latest_market_day():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        if request.url.params["numOfRows"] == "1":
            items = {"item": {"basDt": "20261118", "srtnCd": "005930", "itmsNm": "삼성전자",
                                "mrktCtg": "KOSPI", "mrktTotAmt": "1000000"}}
            total = 1
        else:
            items = {"item": [
                {"basDt": "20261118", "srtnCd": "005930", "itmsNm": "삼성전자",
                 "mrktCtg": "KOSPI", "mrktTotAmt": "1000000"},
                {"basDt": "20261118", "srtnCd": "247540", "itmsNm": "에코프로비엠",
                 "mrktCtg": "KOSDAQ", "mrktTotAmt": "500000"},
                {"basDt": "20261118", "srtnCd": "X", "itmsNm": "채권", "mrktCtg": "KONEX"},
            ]}
            total = 3
        return httpx.Response(200, json={"response": {"header": {"resultCode": "00"},
                                                        "body": {"totalCount": total, "items": items}}})

    client = PublicStockClient("key", "https://example.com", httpx.MockTransport(handler))

    async def run():
        rows = await client.master()
        cached = await client.master()
        await client.close()
        assert rows == cached
        assert [row["code"] for row in rows] == ["005930", "247540"]
        assert rows[0]["market"] == "KOSPI" and rows[1]["market"] == "KOSDAQ"
        assert calls[1]["basDt"] == "20261118" and len(calls) == 2

    asyncio.run(run())


def test_stock_service_uses_public_master_without_kiwoom(fake_redis):
    class Public:
        enabled = True

        async def master(self):
            return [{"code": "005930", "name": "삼성전자", "market": "KOSPI", "sector": "기타",
                     "cap": 1000000, "warning": None}]

    async def run():
        service = StockService(fake_redis, public=Public())
        rows = await service.master()
        assert list(rows) == ["005930"]
        assert service.status()["source"] == "public_data"
        assert service.status()["kiwoom_key"] is False

    asyncio.run(run())


def test_public_stock_daily_parses_and_filters_symbol():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["serviceKey"] == "decoded key"
        assert request.url.params["beginBasDt"] == "20240101"
        assert request.url.params["endBasDt"] == "20240201"
        return httpx.Response(
            200,
            json={
                "response": {
                    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                    "body": {
                        "totalCount": 2,
                        "items": {
                            "item": [
                                {
                                    "basDt": "20240103",
                                    "srtnCd": "005930",
                                    "mkp": "70000",
                                    "hipr": "72000",
                                    "lopr": "69000",
                                    "clpr": "71000",
                                    "trqu": "123456",
                                },
                                {"basDt": "20240103", "srtnCd": "005935", "clpr": "60000"},
                            ]
                        },
                    },
                }
            },
        )

    client = PublicStockClient(
        "decoded%20key",
        "https://apis.data.go.kr/1160100/GetStockSecuritiesInfoService_V2",
        httpx.MockTransport(handler),
    )

    async def run():
        bars = await client.daily("005930", date(2024, 1, 1), date(2024, 1, 31))
        await client.close()
        assert bars == [
            {"date": "2024-01-03", "open": 70000.0, "high": 72000.0, "low": 69000.0,
             "close": 71000.0, "volume": 123456}
        ]

    asyncio.run(run())


def test_public_stock_daily_supports_single_item():
    payload = {
        "response": {
            "header": {"resultCode": "00"},
            "body": {"totalCount": 1, "items": {"item": {"basDt": "20240102", "srtnCd": "000660",
                                                               "mkp": 1, "hipr": 2, "lopr": 1,
                                                               "clpr": 2, "trqu": 3}}},
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps(payload).encode())

    client = PublicStockClient("key", "https://example.com", httpx.MockTransport(handler))

    async def run():
        assert len(await client.daily("000660", date(2024, 1, 1), date(2024, 1, 3))) == 1
        await client.close()

    asyncio.run(run())


def test_latest_uses_last_close_and_cache():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "response": {
                    "header": {"resultCode": "00"},
                    "body": {
                        "totalCount": 1,
                        "items": {"item": {"basDt": "20240131", "srtnCd": "005930", "mkp": 72000,
                                           "hipr": 73000, "lopr": 71000, "clpr": 72700, "trqu": 100}},
                    },
                }
            },
        )

    client = PublicStockClient("key", "https://example.com", httpx.MockTransport(handler))

    async def run():
        first = await client.latest("005930", date(2024, 1, 31))
        second = await client.latest("005930", date(2024, 1, 31))
        await client.close()
        assert first == second
        assert first["price"] == 72700 and first["source"] == "public_data"
        assert first["price_date"] == "2024-01-31" and calls == 1

    asyncio.run(run())
