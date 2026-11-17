"""교육용 가상계좌: 회원가입하면 1,000만 원으로 자동 개설 (예전 가입자는 처음 사용할 때 개설)

- 키움 실제 현재가로 시장가 체결 (키움 연결이 안 되면 가상 시세)
- 현금이 부족하거나 보유 수량이 부족하면 주문 거부
- 수수료 0.015% (매수·매도 각각), 매도 시 실현손익 기록
- 초기화하면 처음 상태로 (거래 기록 삭제)
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.edu.models import EduAccount, EduPosition, EduTrade, EduWatch

INITIAL_CASH = 10_000_000
FEE_PCT = 0.015


class OrderRejected(ValueError):
    pass


def get_or_create(s: Session, user_id: int) -> EduAccount:
    acc = s.get(EduAccount, user_id)
    if not acc:
        acc = EduAccount(user_id=user_id, initial_cash=INITIAL_CASH, cash=INITIAL_CASH)
        s.add(acc)
        s.commit()
    return acc


def place_order(s: Session, user_id: int, symbol: str, side: str, quantity: int, price: float) -> EduTrade:
    if quantity <= 0:
        raise OrderRejected("수량은 1주 이상이어야 해요")
    if price <= 0:
        raise OrderRejected("현재가를 알 수 없어요. 잠시 후 다시 시도해 주세요")
    acc = get_or_create(s, user_id)
    pos = s.scalar(select(EduPosition).where(EduPosition.user_id == user_id, EduPosition.symbol == symbol))
    fee = round(price * quantity * FEE_PCT / 100)
    pnl = None

    if side == "buy":
        cost = price * quantity + fee
        if cost > acc.cash:
            can = int(acc.cash // (price * (1 + FEE_PCT / 100)))
            raise OrderRejected(f"현금이 부족해요. 지금은 최대 {can}주까지 살 수 있어요")
        acc.cash -= cost
        if pos:
            pos.avg_price = (pos.avg_price * pos.quantity + price * quantity) / (pos.quantity + quantity)
            pos.quantity += quantity
        else:
            s.add(EduPosition(user_id=user_id, symbol=symbol, quantity=quantity, avg_price=price))
    elif side == "sell":
        held = pos.quantity if pos else 0
        if quantity > held:
            raise OrderRejected(f"보유 수량이 부족해요. 지금 {held}주 가지고 있어요")
        acc.cash += price * quantity - fee
        pnl = round((price - pos.avg_price) * quantity - fee)
        pos.quantity -= quantity
        if pos.quantity == 0:
            s.delete(pos)
    else:
        raise OrderRejected("side는 buy 또는 sell")

    trade = EduTrade(
        user_id=user_id, symbol=symbol, side=side, quantity=quantity, price=price, fee=fee, realized_pnl=pnl
    )
    s.add(trade)
    s.commit()
    return trade


def reset(s: Session, user_id: int) -> None:
    for model in (EduPosition, EduTrade):
        s.execute(delete(model).where(model.user_id == user_id))
    acc = get_or_create(s, user_id)
    acc.cash = acc.initial_cash
    s.commit()


def snapshot(s: Session, user_id: int, prices: dict[str, dict]) -> dict:
    """계좌 요약. prices: 종목코드 → 최신 시세(dict, name·price 포함)"""
    acc = get_or_create(s, user_id)
    positions = []
    for p in s.scalars(select(EduPosition).where(EduPosition.user_id == user_id).order_by(EduPosition.symbol)):
        now = prices.get(p.symbol, {}).get("price", p.avg_price)
        value = now * p.quantity
        positions.append(
            {
                "symbol": p.symbol,
                "name": prices.get(p.symbol, {}).get("name", p.symbol),
                "quantity": p.quantity,
                "avg_price": round(p.avg_price),
                "price": now,
                "value": round(value),
                "pnl": round((now - p.avg_price) * p.quantity),
                "return_pct": round((now / p.avg_price - 1) * 100, 2),
            }
        )
    stock_value = sum(x["value"] for x in positions)
    equity = acc.cash + stock_value
    trades = s.scalars(select(EduTrade).where(EduTrade.user_id == user_id).order_by(EduTrade.id.desc()).limit(30))
    realized = s.scalars(select(EduTrade.realized_pnl).where(EduTrade.user_id == user_id, EduTrade.side == "sell"))
    return {
        "initial_cash": acc.initial_cash,
        "cash": round(acc.cash),
        "stock_value": stock_value,
        "equity": round(equity),
        "return_pct": round((equity / acc.initial_cash - 1) * 100, 2),
        "realized_pnl": round(sum(x or 0 for x in realized)),
        "positions": positions,
        "trades": [
            {
                "id": t.id,
                "symbol": t.symbol,
                "name": prices.get(t.symbol, {}).get("name", t.symbol),
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "fee": t.fee,
                "realized_pnl": t.realized_pnl,
                "created_at": t.created_at.isoformat(),
            }
            for t in trades
        ],
    }


def symbols(s: Session, user_id: int) -> list[str]:
    """평가·표시에 시세가 필요한 종목 (보유 + 최근 거래)"""
    held = s.scalars(select(EduPosition.symbol).where(EduPosition.user_id == user_id))
    traded = s.scalars(
        select(EduTrade.symbol).where(EduTrade.user_id == user_id).order_by(EduTrade.id.desc()).limit(30)
    )
    return list(dict.fromkeys([*held, *traded]))


# ---------- 관심종목 ----------
MAX_WATCH = 30


def watchlist(s: Session, user_id: int) -> list[str]:
    return list(s.scalars(select(EduWatch.symbol).where(EduWatch.user_id == user_id).order_by(EduWatch.id)))


def add_watch(s: Session, user_id: int, symbol: str) -> list[str]:
    current = watchlist(s, user_id)
    if symbol not in current:
        if len(current) >= MAX_WATCH:
            raise OrderRejected(f"관심종목은 최대 {MAX_WATCH}개까지 담을 수 있어요")
        s.add(EduWatch(user_id=user_id, symbol=symbol))
        s.commit()
    return watchlist(s, user_id)


def remove_watch(s: Session, user_id: int, symbol: str) -> list[str]:
    s.execute(delete(EduWatch).where(EduWatch.user_id == user_id, EduWatch.symbol == symbol))
    s.commit()
    return watchlist(s, user_id)
