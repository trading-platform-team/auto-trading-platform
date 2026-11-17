import io
import zipfile
from datetime import date

import httpx
import pytest

from app.history.external_events import fetch_disclosure_preview, fetch_disclosures, fetch_news


@pytest.mark.asyncio
async def test_opendart_disclosure_is_converted(monkeypatch):
    monkeypatch.setattr("app.history.external_events.settings.opendart_api_key", "dart-key")

    def handler(request):
        assert request.url.params["corp_code"] == "00126380"
        return httpx.Response(
            200,
            json={
                "status": "000",
                "list": [
                    {
                        "rcept_no": "20240430000123",
                        "rcept_dt": "20240430",
                        "report_nm": "분기보고서",
                        "flr_nm": "삼성전자",
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        events = await fetch_disclosures("005930", date(2024, 4, 1), date(2024, 4, 30), client)
    assert events[0]["id"] == "dart-20240430000123"
    assert events[0]["date"] == "2024-04-30"
    assert events[0]["impact"] == "mixed"


@pytest.mark.asyncio
async def test_naver_news_filters_period_and_removes_html(monkeypatch):
    monkeypatch.setattr("app.history.external_events.settings.naver_news_client_id", "naver-id")
    monkeypatch.setattr("app.history.external_events.settings.naver_news_client_secret", "naver-secret")

    def handler(request):
        assert request.headers["X-NCP-APIGW-API-KEY-ID"] == "naver-id"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "title": "<b>삼성전자</b> 실적 발표",
                        "description": "매출이 &amp; 영업이익이 발표됐습니다.",
                        "originallink": "https://example.com/news/1",
                        "pubDate": "Tue, 30 Apr 2024 09:00:00 +0900",
                    },
                    {
                        "title": "기간 밖 기사",
                        "description": "제외",
                        "link": "https://example.com/news/2",
                        "pubDate": "Wed, 01 May 2025 09:00:00 +0900",
                    },
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        events = await fetch_news("005930", date(2024, 4, 1), date(2024, 4, 30), client)
    assert len(events) == 1
    assert events[0]["title"] == "삼성전자 실적 발표"
    assert events[0]["summary"] == "매출이 & 영업이익이 발표됐습니다."


@pytest.mark.asyncio
async def test_disclosure_preview_extracts_text(monkeypatch):
    monkeypatch.setattr("app.history.external_events.settings.opendart_api_key", "dart-key")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "20240430000123.xml",
            "<html><style>숨길 내용</style><body><h1>신규 시설투자</h1><p>투자금액 1조원</p></body></html>",
        )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=buffer.getvalue()))
    async with httpx.AsyncClient(transport=transport) as client:
        preview = await fetch_disclosure_preview("20240430000123", client)
    assert "신규 시설투자" in preview["content"]
    assert "투자금액 1조원" in preview["content"]
    assert "숨길 내용" not in preview["content"]

