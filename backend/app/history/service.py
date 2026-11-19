"""과거 시세 조회·적재"""

from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.history.models import PriceBar
from app.history.synthetic import generate_daily
from app.market.sources import DEFAULT_SYMBOLS

SEED_START, SEED_END = date(2023, 1, 2), date(2025, 12, 31)


def ensure_seeded(s: Session) -> int:
    """비어 있으면 가상 일봉을 채운다. 추가된 행 수를 돌려준다."""
    if s.scalar(select(func.count()).select_from(PriceBar)):
        return 0
    rows = []
    for symbol, (_, base) in DEFAULT_SYMBOLS.items():
        rows += generate_daily(symbol, base, SEED_START, SEED_END)
    s.bulk_insert_mappings(PriceBar, [{**r, "source": "synthetic"} for r in rows])
    s.commit()
    return len(rows)


def seed_symbol(s: Session, symbol: str, base_price: float) -> int:
    """기본 종목이 아닌 종목에 가상 일봉을 채운다 (공공데이터 일봉을 못 받았을 때). 이미 있으면 그대로 둔다."""
    if s.scalar(select(func.count()).select_from(PriceBar).where(PriceBar.symbol == symbol)):
        return 0
    rows = generate_daily(symbol, base_price, SEED_START, SEED_END)
    s.bulk_insert_mappings(PriceBar, [{**r, "source": "synthetic"} for r in rows])
    s.commit()
    return len(rows)


def load_bars(s: Session, symbol: str, start: date | None = None, end: date | None = None) -> list[dict]:
    q = select(PriceBar).where(PriceBar.symbol == symbol)
    if start:
        q = q.where(PriceBar.date >= start)
    if end:
        q = q.where(PriceBar.date <= end)
    return [
        {
            "date": b.date.isoformat(),
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
            "source": b.source,
        }
        for b in s.scalars(q.order_by(PriceBar.date))
    ]


async def sync_public_bars(s: Session, stocks, symbol: str, start: date, end: date) -> int:
    """금융위원회 실제 일봉을 저장한다. 성공한 종목의 기존 가상 일봉은 제거한다."""
    bars = await stocks.daily(symbol, start, end)
    if not bars:
        return 0

    existing = {
        row.date: row
        for row in s.scalars(
            select(PriceBar).where(
                PriceBar.symbol == symbol,
                PriceBar.source == "public_data",
                PriceBar.date >= start,
                PriceBar.date <= end,
            )
        )
    }
    s.execute(delete(PriceBar).where(PriceBar.symbol == symbol, PriceBar.source != "public_data"))
    for bar in bars:
        day = date.fromisoformat(bar["date"])
        row = existing.get(day)
        if row is None:
            row = PriceBar(symbol=symbol, date=day)
            s.add(row)
        row.open = bar["open"]
        row.high = bar["high"]
        row.low = bar["low"]
        row.close = bar["close"]
        row.volume = bar["volume"]
        row.source = "public_data"
    s.commit()
    return len(bars)


def symbols_summary(s: Session) -> list[dict]:
    q = (
        select(
            PriceBar.symbol, func.min(PriceBar.date), func.max(PriceBar.date), func.count(), func.max(PriceBar.source)
        )
        .group_by(PriceBar.symbol)
        .order_by(PriceBar.symbol)
    )
    return [
        {
            "symbol": sym,
            "name": DEFAULT_SYMBOLS.get(sym, (sym,))[0],
            "start": a.isoformat(),
            "end": b.isoformat(),
            "count": n,
            "source": src,
        }
        for sym, a, b, n, src in s.execute(q)
    ]
