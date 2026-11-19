from datetime import date

import httpx
import pytest

from app.history.kis_minutes import KisMinuteClient


@pytest.mark.asyncio
async def test_kis_minute_replay_parses_and_caches():
    calls = {"token": 0, "minutes": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            calls["token"] += 1
            return httpx.Response(200, json={"access_token": "safe-token", "expires_in": 3600})
        calls["minutes"] += 1
        assert request.headers["tr_id"] == "FHKST03010230"
        return httpx.Response(200, json={
            "rt_cd": "0", "msg1": "정상처리 되었습니다.",
            "output2": [
                {"stck_cntg_hour": "090100", "stck_prpr": "70100", "stck_oprc": "70000",
                 "stck_hgpr": "70200", "stck_lwpr": "69900", "cntg_vol": "15"},
                {"stck_cntg_hour": "090000", "stck_prpr": "70000", "stck_oprc": "70000",
                 "stck_hgpr": "70100", "stck_lwpr": "69900", "cntg_vol": "10"},
            ],
        })

    client = KisMinuteClient("key", "secret", "https://example.test", transport=httpx.MockTransport(handler))
    try:
        rows = await client.minutes("005930")
        again = await client.minutes("005930")
        assert rows is again
        assert [row["price"] for row in rows] == [70000, 70100]
        assert rows[0]["source"] == "kis_replay"
        assert calls == {"token": 1, "minutes": 1}
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_kis_disabled_does_not_call_network():
    client = KisMinuteClient("", "", "https://example.test")
    try:
        assert not client.enabled
        assert await client.replay_quote("005930") is None
    finally:
        await client.close()
