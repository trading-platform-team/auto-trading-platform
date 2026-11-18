import asyncio
import json
from datetime import date

import httpx

from app.history.public_data import PublicStockClient


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
