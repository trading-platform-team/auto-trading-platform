"""타임머신 교육용 주요 사건 데이터.

기업·기관의 공식 발표만 요약하며, 사건과 주가 움직임의 인과관계는 단정하지 않는다.
symbol이 None인 사건은 전체 종목에 공통으로 노출되는 시장 사건이다.
"""

from datetime import date

EVENTS = (
    {
        "id": "bok-2024-01-hold",
        "date": "2024-01-11",
        "symbol": None,
        "category": "금리",
        "title": "한국은행 기준금리 3.50% 유지",
        "summary": (
            "한국은행 금융통화위원회가 기준금리를 3.50%로 유지했습니다. "
            "금리 수준은 기업 자금조달 비용과 투자심리에 영향을 줄 수 있습니다."
        ),
        "impact": "mixed",
        "source_name": "한국은행",
        "source_url": "https://www.bok.or.kr/eng/bbs/E0000634/view.do?menuNo=400069&nttId=10081737",
    },
    {
        "id": "skhynix-2024-q1",
        "date": "2024-04-25",
        "symbol": "000660",
        "category": "실적",
        "title": "SK하이닉스 2024년 1분기 실적 발표",
        "summary": (
            "매출 12조 4,296억 원, 영업이익 2조 8,860억 원을 발표했습니다. "
            "AI 메모리 수요와 NAND 사업의 흑자 전환을 주요 배경으로 설명했습니다."
        ),
        "impact": "positive",
        "source_name": "SK하이닉스 뉴스룸",
        "source_url": "https://news.skhynix.com/en/sk-hynix-announces-1q24-financial-results/",
    },
    {
        "id": "hyundai-2024-q1",
        "date": "2024-04-25",
        "symbol": "005380",
        "category": "실적",
        "title": "현대자동차 2024년 1분기 경영실적 발표",
        "summary": (
            "1분기 매출은 전년 동기 대비 7.6% 증가한 40조 6,585억 원, "
            "영업이익은 2.3% 감소한 3조 5,574억 원을 기록했습니다."
        ),
        "impact": "mixed",
        "source_name": "현대자동차 뉴스룸",
        "source_url": "https://www.hyundai.com/worldwide/en/newsroom/detail/hyundai-motor-announces-2024-q1-business-results-0000000755",
    },
    {
        "id": "samsung-2024-q1",
        "date": "2024-04-30",
        "symbol": "005930",
        "category": "실적",
        "title": "삼성전자 2024년 1분기 실적 발표",
        "summary": (
            "매출 71조 9,200억 원, 영업이익 6조 6,100억 원을 발표했습니다. "
            "메모리 사업의 흑자 전환과 갤럭시 S24 판매가 실적에 기여했습니다."
        ),
        "impact": "positive",
        "source_name": "삼성전자 뉴스룸",
        "source_url": "https://news.samsung.com/kr/%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90-2024%EB%85%84-1%EB%B6%84%EA%B8%B0-%EC%8B%A4%EC%A0%81-%EB%B0%9C%ED%91%9C",
    },
    {
        "id": "naver-2024-q1",
        "date": "2024-05-03",
        "symbol": "035420",
        "category": "실적",
        "title": "네이버 2024년 1분기 실적 발표",
        "summary": (
            "매출 2조 5,261억 원, 영업이익 4,393억 원을 기록했습니다. "
            "서치플랫폼과 커머스 등 주요 사업 부문의 성장을 설명했습니다."
        ),
        "impact": "positive",
        "source_name": "NAVER",
        "source_url": "https://navercorp.com/media/pressReleasesDetail?seq=31753",
    },
    {
        "id": "kakao-2024-q1",
        "date": "2024-05-09",
        "symbol": "035720",
        "category": "실적",
        "title": "카카오 2024년 1분기 실적 발표",
        "summary": (
            "매출 1조 9,884억 원, 영업이익 1,203억 원을 발표했습니다. "
            "전년 동기 대비 매출은 22%, 영업이익은 92% 증가했습니다."
        ),
        "impact": "positive",
        "source_name": "카카오",
        "source_url": "https://www.kakaocorp.com/page/detail/11021",
    },
    {
        "id": "bok-2024-10-cut",
        "date": "2024-10-11",
        "symbol": None,
        "category": "금리",
        "title": "한국은행 기준금리 3.25%로 인하",
        "summary": (
            "한국은행 금융통화위원회가 기준금리를 3.50%에서 3.25%로 0.25%포인트 인하했습니다. "
            "금리 인하는 시장 유동성과 업종별 투자심리에 다르게 작용할 수 있습니다."
        ),
        "impact": "mixed",
        "source_name": "한국은행",
        "source_url": "https://www.bok.or.kr/eng/bbs/E0000627/view.do?menuNo=400022&nttId=10087411",
    },
)


def load_events(symbol: str, start: date | None = None, end: date | None = None) -> list[dict]:
    """종목 사건과 시장 공통 사건을 기간순으로 반환한다."""
    start_iso = start.isoformat() if start else None
    end_iso = end.isoformat() if end else None
    return [
        {**event, "educational_note": "사건과 주가 움직임을 함께 살펴보는 학습 자료이며, 인과관계를 단정하지 않습니다."}
        for event in EVENTS
        if event["symbol"] in (None, symbol)
        and (start_iso is None or event["date"] >= start_iso)
        and (end_iso is None or event["date"] <= end_iso)
    ]


def merge_events(*groups: list[dict]) -> list[dict]:
    """URL과 제목·날짜가 같은 사건을 제거하고 시간순으로 합친다."""
    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for event in (event for group in groups for event in group):
        key = (event.get("source_url", ""), f"{event['date']}:{event['title']}")
        if key[0] in {item[0] for item in seen if item[0]} or key in seen:
            continue
        seen.add(key)
        merged.append(event)
    return sorted(merged, key=lambda item: (item["date"], item["id"]))
