"""OpenDART 공시와 NAVER API HUB 뉴스를 타임머신 사건 형식으로 변환한다."""

import html
import io
import re
import zipfile
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

import httpx

from app.core.config import settings

COMPANIES = {
    "005930": ("삼성전자", "00126380"),
    "000660": ("SK하이닉스", "00164779"),
    "005380": ("현대자동차", "00164742"),
    "035420": ("NAVER", "00266961"),
    "035720": ("카카오", "00258801"),
}
EDUCATIONAL_NOTE = "공시·뉴스와 주가 움직임을 함께 살펴보는 학습 자료이며, 인과관계를 단정하지 않습니다."
TAG_RE = re.compile(r"<[^>]+>")
MAJOR_TERMS = (
    "실적",
    "매출",
    "영업이익",
    "사업보고서",
    "분기보고서",
    "반기보고서",
    "투자",
    "인수",
    "합병",
    "분할",
    "증자",
    "감자",
    "배당",
    "자기주식",
    "최대주주",
    "계약",
    "공급",
    "출시",
    "증설",
    "소송",
)
MAX_DISCLOSURE_EVENTS = 3
MAX_NEWS_EVENTS = 3
MAX_PREVIEW_ARCHIVE_BYTES = 10 * 1024 * 1024
MAX_PREVIEW_DOCUMENT_BYTES = 2 * 1024 * 1024
MAX_PREVIEW_CHARS = 3000
CORE_DISCLOSURE_TERMS = (
    "잠정",
    "매출액또는손익구조",
    "사업보고서",
    "분기보고서",
    "반기보고서",
    "신규시설투자",
    "단일판매",
    "공급계약",
    "합병",
    "분할",
    "영업양도",
    "유상증자",
    "무상증자",
    "감자",
    "현금ㆍ현물배당",
    "최대주주변경",
)


class DisclosurePreviewParser(HTMLParser):
    """DART HTML/XML 원문에서 이미지 미리보기용 텍스트를 추출한다."""

    BLOCKS = {"br", "div", "p", "tr", "table", "h1", "h2", "h3", "h4", "li"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipped = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"style", "script"}:
            self.skipped += 1
        elif not self.skipped and tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script"} and self.skipped:
            self.skipped -= 1
        elif not self.skipped and tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skipped and data.strip():
            self.parts.append(data.strip() + " ")

    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self.parts).splitlines())
        return "\n".join(line for line in lines if line)[:MAX_PREVIEW_CHARS]


def _text(value: str | None, limit: int = 300) -> str:
    cleaned = TAG_RE.sub("", html.unescape(value or ""))
    return " ".join(cleaned.split())[:limit]


def _period(start: date | None, end: date | None) -> tuple[date, date]:
    period_end = end or date.today()
    return start or period_end - timedelta(days=90), period_end


def _valid_url(value: str | None) -> str:
    return value if value and value.startswith(("https://", "http://")) else ""


def _disclosure_summary(report_name: str, filer: str) -> str:
    """공시 제목을 초보자가 이해할 수 있는 짧은 설명으로 바꾼다."""
    explanations = (
        (("최대주주", "대량보유"), "주요 주주의 보유 주식 수나 지분율이 변경됐다는 공시입니다."),
        (
            ("사업보고서", "분기보고서", "반기보고서", "실적"),
            "회사의 매출·이익과 재무상태를 확인할 수 있는 실적 관련 공시입니다.",
        ),
        (("투자설명서",), "투자 조건과 위험요인 등 투자자가 알아야 할 내용을 설명한 공시입니다."),
        (("유상증자", "무상증자", "감자"), "회사가 주식 수나 자본금을 변경하는 내용의 공시입니다."),
        (("배당",), "회사가 주주에게 이익을 나누는 배당 관련 공시입니다."),
        (("자기주식",), "회사가 자기 회사 주식을 취득하거나 처분하는 내용의 공시입니다."),
        (("계약", "공급"), "회사의 매출에 영향을 줄 수 있는 계약이나 공급 관련 공시입니다."),
        (("합병", "분할", "인수"), "회사의 사업 또는 지배구조가 바뀔 수 있는 공시입니다."),
    )
    for keywords, explanation in explanations:
        if any(keyword in report_name for keyword in keywords):
            return f"{explanation} 정확한 수치와 사유는 원문에서 확인하세요."
    return f"{filer}에서 제출한 주요 전자공시입니다. 자세한 내용은 원문에서 확인하세요."


def _disclosure_priority(report_name: str) -> int:
    """초보자에게 우선 보여줄 공시일수록 높은 점수를 준다."""
    priorities = (
        (("잠정", "매출액또는손익구조"), 6),
        (("신규시설투자", "단일판매", "공급계약", "합병", "분할", "영업양도"), 5),
        (("사업보고서", "분기보고서", "반기보고서"), 4),
        (("배당", "유상증자", "무상증자", "감자"), 3),
        (("최대주주변경",), 2),
    )
    return next((score for keywords, score in priorities if any(word in report_name for word in keywords)), 0)


async def fetch_disclosures(
    symbol: str,
    start: date | None,
    end: date | None,
    client: httpx.AsyncClient,
) -> list[dict]:
    company = COMPANIES.get(symbol)
    if not company or not settings.opendart_api_key:
        return []
    _, corp_code = company
    period_start, period_end = _period(start, end)
    response = await client.get(
        "https://opendart.fss.or.kr/api/list.json",
        params={
            "crtfc_key": settings.opendart_api_key,
            "corp_code": corp_code,
            "bgn_de": period_start.strftime("%Y%m%d"),
            "end_de": period_end.strftime("%Y%m%d"),
            "page_count": 100,
            "sort": "date",
            "sort_mth": "asc",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") == "013":
        return []
    if payload.get("status") != "000":
        raise ValueError(f"OpenDART 오류: {payload.get('message', '알 수 없음')}")
    events = [
        {
            "id": f"dart-{item['rcept_no']}",
            "date": f"{item['rcept_dt'][:4]}-{item['rcept_dt'][4:6]}-{item['rcept_dt'][6:8]}",
            "symbol": symbol,
            "category": "공시",
            "title": _text(item.get("report_nm"), 160),
            "summary": _disclosure_summary(_text(item.get("report_nm"), 160), _text(item.get("flr_nm"), 80)),
            "impact": "mixed",
            "source_name": "OpenDART",
            "source_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item['rcept_no']}",
            "rcept_no": item["rcept_no"],
            "educational_note": EDUCATIONAL_NOTE,
        }
        for item in payload.get("list", [])
        if item.get("rcept_no") and len(item.get("rcept_dt", "")) == 8
        and any(term in item.get("report_nm", "") for term in CORE_DISCLOSURE_TERMS)
    ]
    latest_by_title = {event["title"].strip(): event for event in events}
    return sorted(
        latest_by_title.values(),
        key=lambda event: (_disclosure_priority(event["title"]), event["date"]),
        reverse=True,
    )[:MAX_DISCLOSURE_EVENTS]


async def fetch_news(
    symbol: str,
    start: date | None,
    end: date | None,
    client: httpx.AsyncClient,
) -> list[dict]:
    company = COMPANIES.get(symbol)
    if not company or not settings.naver_news_client_id or not settings.naver_news_client_secret:
        return []
    name, _ = company
    period_start, period_end = _period(start, end)
    response = await client.get(
        "https://naverapihub.apigw.ntruss.com/search/v1/news",
        params={"query": name, "display": 100, "start": 1, "sort": "date", "format": "json"},
        headers={
            "X-NCP-APIGW-API-KEY-ID": settings.naver_news_client_id,
            "X-NCP-APIGW-API-KEY": settings.naver_news_client_secret,
        },
    )
    response.raise_for_status()
    events = []
    for index, item in enumerate(response.json().get("items", [])):
        try:
            published = parsedate_to_datetime(item["pubDate"]).date()
        except (KeyError, TypeError, ValueError):
            continue
        if not period_start <= published <= period_end:
            continue
        source_url = _valid_url(item.get("originallink")) or _valid_url(item.get("link"))
        if not source_url:
            continue
        searchable = f"{_text(item.get('title'))} {_text(item.get('description'))}"
        if not any(term in searchable for term in MAJOR_TERMS):
            continue
        events.append(
            {
                "id": f"naver-{symbol}-{published:%Y%m%d}-{index}",
                "date": published.isoformat(),
                "symbol": symbol,
                "category": "뉴스",
                "title": _text(item.get("title"), 160),
                "summary": _text(item.get("description")) or "기사 원문에서 자세한 내용을 확인하세요.",
                "impact": "mixed",
                "source_name": "NAVER 뉴스",
                "source_url": source_url,
                "educational_note": EDUCATIONAL_NOTE,
            }
        )
        if len(events) >= MAX_NEWS_EVENTS:
            break
    return events

async def load_external_events(symbol: str, start: date | None = None, end: date | None = None) -> list[dict]:
    """외부 서비스가 실패해도 화면을 깨뜨리지 않고 수집된 사건만 반환한다."""
    if not settings.external_events_enabled:
        return []
    events: list[dict] = []
    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
        for loader in (fetch_disclosures, fetch_news):
            try:
                events.extend(await loader(symbol, start, end, client))
            except (httpx.HTTPError, KeyError, TypeError, ValueError):
                continue
    return events


async def fetch_disclosure_preview(rcept_no: str, client: httpx.AsyncClient | None = None) -> dict:
    """선택한 공시 원문에서 브라우저 이미지 생성용 텍스트 일부를 반환한다."""
    if not settings.opendart_api_key:
        raise ValueError("OpenDART 인증키가 설정되지 않았습니다")
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=10, follow_redirects=True)
    try:
        response = await client.get(
            "https://opendart.fss.or.kr/api/document.xml",
            params={"crtfc_key": settings.opendart_api_key, "rcept_no": rcept_no},
        )
        response.raise_for_status()
        if len(response.content) > MAX_PREVIEW_ARCHIVE_BYTES:
            raise ValueError("미리보기를 만들기에는 공시 파일이 너무 큽니다")
        try:
            archive = zipfile.ZipFile(io.BytesIO(response.content))
        except zipfile.BadZipFile as exc:
            raise ValueError("공시 원문을 불러오지 못했습니다") from exc
        names = [name for name in archive.namelist() if name.lower().endswith((".xml", ".html", ".htm"))]
        if not names:
            raise ValueError("미리보기 가능한 공시 문서가 없습니다")
        entry = archive.getinfo(names[0])
        with archive.open(entry) as document_file:
            raw = document_file.read(MAX_PREVIEW_DOCUMENT_BYTES)
        try:
            document = raw.decode("utf-8")
        except UnicodeDecodeError:
            document = raw.decode("euc-kr", errors="replace")
        parser = DisclosurePreviewParser()
        parser.feed(document)
        content = parser.text()
        if not content:
            raise ValueError("공시에서 미리보기 내용을 찾지 못했습니다")
        return {"rcept_no": rcept_no, "content": content}
    finally:
        if owns_client:
            await client.aclose()


