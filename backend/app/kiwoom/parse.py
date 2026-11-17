"""키움 응답 값 변환

키움은 숫자를 문자열로 주고, 현재가·대비·거래량 등에 방향 부호를 붙인다. 예) "+72000", "-000150", "0.00"
종목코드는 계좌 조회에서 접두어가 붙어 온다. 예) "A005930"
"""


def to_num(value) -> float:
    """'+72,000' → 72000.0, '-1.5' → -1.5, '' / None → 0.0"""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "")
    if not s:
        return 0.0
    sign = -1.0 if s.startswith("-") else 1.0
    s = s.lstrip("+-")
    try:
        return sign * float(s) if s else 0.0
    except ValueError:
        return 0.0


def to_int(value) -> int:
    return int(to_num(value))


def price(value) -> int:
    """가격 필드: 부호는 전일 대비 방향일 뿐이므로 절댓값"""
    return abs(to_int(value))


def qty(value) -> int:
    """거래량 필드: 부호는 매수(+)/매도(-) 체결 구분이므로 절댓값"""
    return abs(to_int(value))


def code(value) -> str:
    """'A005930' → '005930', '005930_NX' → '005930'"""
    s = str(value or "").strip()
    if s[:1].isalpha() and len(s) == 7:
        s = s[1:]
    return s.split("_")[0]
