"""교육 커리큘럼 목록 (레슨 순서·XP·잠금 규칙은 서버가 관리)

레슨 화면 내용(카드, 퀴즈)은 프론트엔드 frontend/src/components/education/content/ 에 있고,
여기의 id와 같은 키로 연결된다. available=False 인 레슨은 '준비 중'으로 표시된다.
"""

UNITS = [
    {
        "id": "u1",
        "title": "주식 첫걸음",
        "description": "주식이 뭔지, 가격을 어떻게 읽는지, 어떻게 사고파는지",
        "lessons": [
            {"id": "u1-l1", "title": "주식이란?", "available": True},
            {"id": "u1-l2", "title": "가격 읽기", "available": True},
            {"id": "u1-l3", "title": "사고팔기", "available": True},
            {"id": "u1-l4", "title": "내 계좌 읽기", "available": True},
        ],
    },
    {
        "id": "u2",
        "title": "차트 읽기",
        "description": "캔들, 추세, 거래량, 이동평균선",
        "lessons": [
            {"id": "u2-l1", "title": "캔들 차트", "available": True},
            {"id": "u2-l2", "title": "추세", "available": True},
            {"id": "u2-l3", "title": "거래량", "available": True},
            {"id": "u2-l4", "title": "이동평균선", "available": True},
        ],
    },
    {
        "id": "u3",
        "title": "기술적 지표",
        "description": "RSI, 볼린저밴드, 골든크로스",
        "lessons": [
            {"id": "u3-l1", "title": "RSI", "available": True},
            {"id": "u3-l2", "title": "볼린저밴드", "available": True},
            {"id": "u3-l3", "title": "골든크로스·데드크로스", "available": True},
        ],
    },
    {
        "id": "u4",
        "title": "유명 매매 전략",
        "description": "대표 전략을 백테스트로 비교해 보기",
        "lessons": [
            {"id": "u4-l1", "title": "추세 추종 전략", "available": True},
            {"id": "u4-l2", "title": "역추세 전략", "available": True},
        ],
    },
    {
        "id": "u5",
        "title": "리스크 관리",
        "description": "손익비, 손절·익절, 투자 비중",
        "lessons": [
            {"id": "u5-l1", "title": "손절과 익절", "available": True},
            {"id": "u5-l2", "title": "손익비", "available": True},
            {"id": "u5-l3", "title": "투자 비중", "available": True},
        ],
    },
    {
        "id": "u6",
        "title": "자동매매 설정",
        "description": "배운 내용으로 나만의 자동매매 전략 만들기",
        "lessons": [
            {"id": "u6-l1", "title": "조건 만들기", "available": True},
            {"id": "u6-l2", "title": "내 첫 자동매매", "available": True},
        ],
    },
]

LESSON_XP = 10
PERFECT_BONUS = 5
ORDER = [lesson["id"] for unit in UNITS for lesson in unit["lessons"]]


def lesson(lesson_id: str) -> dict | None:
    return next((x for u in UNITS for x in u["lessons"] if x["id"] == lesson_id), None)


def previous(lesson_id: str) -> str | None:
    i = ORDER.index(lesson_id)
    return ORDER[i - 1] if i > 0 else None


def unit_of(lesson_id: str) -> dict:
    return next(u for u in UNITS if any(x["id"] == lesson_id for x in u["lessons"]))
