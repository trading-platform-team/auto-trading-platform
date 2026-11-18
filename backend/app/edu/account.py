"""교육용 가상계좌: 회원가입하면 1,000만 원으로 자동 개설 (예전 가입자는 처음 사용할 때 개설)

- 직접 주문: 키움 실제 현재가로 시장가 체결 (키움 연결이 안 되면 가상 시세)
- 자동매매 주문(모의 전략): strategy/broker.py 의 PaperBroker가 전략이 본 시세로 같은 계좌에 체결
- 현금이 부족하거나 보유 수량이 부족하면 주문 거부
- 수수료 0.015% (매수·매도 각각), 매도 시 실현손익 기록
- 초기화하면 처음 상태로 (거래 기록과 자동매매 모의 주문 내역 삭제, 전략·키움 실주문은 그대로)
- 거래 기록에 직접 주문 / 자동매매(전략 이름) 구분, 전략별 통계 (거래 수·실현손익·승률)
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.edu.models import EduAccount, EduPosition, EduTrade, EduWatch
from app.strategy.models import Order, Strategy

INITIAL_CASH = 10_000_000
FEE_PCT = 0.015


class OrderRejected(ValueError):
    pass


def realized_pnl(avg_price: float, price: float, quantity: int, sell_fee: float) -> int:
    """매도 실현손익 = 매도 금액 − 매도 수수료 − (매입 금액 + 매수 수수료)

    평균 단가에는 수수료가 들어 있지 않으므로, 판 수량만큼의 매수 수수료를 평균 단가 기준으로 계산해 뺀다.
    (매수할 때마다 원 단위로 반올림한 실제 수수료와는 1원 안팎 차이가 날 수 있다)
    """
    buy_fee = avg_price * quantity * FEE_PCT / 100
    return round((price - avg_price) * quantity - sell_fee - buy_fee)


def get_or_create(s: Session, user_id: int) -> EduAccount:
    acc = s.get(EduAccount, user_id)
    if not acc:
        acc = EduAccount(user_id=user_id, initial_cash=INITIAL_CASH, cash=INITIAL_CASH)
        s.add(acc)
        s.commit()
    return acc


def place_order(
    s: Session,
    user_id: int,
    symbol: str,
    side: str,
    quantity: int,
    price: float,
    strategy_id: int | None = None,
    commit: bool = True,
) -> EduTrade:
    """시장가 주문. 거부할 때는 계좌를 바꾸기 전에 OrderRejected를 올린다.

    strategy_id: 자동매매 주문이면 전략 ID (직접 주문은 None)
    commit=False: 호출한 쪽이 다른 기록(주문 내역 등)과 함께 한 번에 커밋할 때
    """
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
        pnl = realized_pnl(pos.avg_price, price, quantity, fee)
        pos.quantity -= quantity
        if pos.quantity == 0:
            s.delete(pos)
    else:
        raise OrderRejected("side는 buy 또는 sell")

    trade = EduTrade(
        user_id=user_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        fee=fee,
        realized_pnl=pnl,
        strategy_id=strategy_id,
    )
    s.add(trade)
    if commit:
        s.commit()
    else:
        s.flush()  # trade.id를 바로 쓸 수 있게
    return trade


def reset(s: Session, user_id: int) -> None:
    # Order: 자동매매 모의 주문 내역 (이 계좌로 체결된 기록이라 같이 지움). 키움 실주문은 별도 테이블
    for model in (EduPosition, EduTrade, Order):
        s.execute(delete(model).where(model.user_id == user_id))
    acc = get_or_create(s, user_id)
    acc.cash = acc.initial_cash
    s.commit()


def strategy_names(s: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return dict(s.execute(select(Strategy.id, Strategy.name).where(Strategy.id.in_(ids))).all())


def strategy_stats(s: Session, user_id: int) -> list[dict]:
    """직접 주문과 전략별 성과: 거래 수, 매수·매도 수, 실현손익, 승률(수익 난 매도 / 전체 매도)

    직접 주문이 맨 앞, 나머지는 거래가 많은 전략 순. 삭제된 전략도 기록은 남는다.
    """
    groups: dict[int | None, dict] = {}
    for strategy_id, side, pnl in s.execute(
        select(EduTrade.strategy_id, EduTrade.side, EduTrade.realized_pnl).where(EduTrade.user_id == user_id)
    ):
        g = groups.setdefault(strategy_id, {"trades": 0, "buys": 0, "sells": 0, "wins": 0, "realized_pnl": 0.0})
        g["trades"] += 1
        if side == "buy":
            g["buys"] += 1
        else:
            g["sells"] += 1
            g["wins"] += 1 if (pnl or 0) > 0 else 0
            g["realized_pnl"] += pnl or 0
    names = strategy_names(s, {k for k in groups if k is not None})
    rows = [
        {
            "strategy_id": k,
            "name": "직접 주문" if k is None else names.get(k, "삭제된 전략"),
            "auto": k is not None,
            **g,
            "realized_pnl": round(g["realized_pnl"]),
            "win_rate": round(g["wins"] / g["sells"] * 100, 1) if g["sells"] else None,
        }
        for k, g in groups.items()
    ]
    return sorted(rows, key=lambda x: (x["auto"], -x["trades"]))


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
    trades = list(
        s.scalars(select(EduTrade).where(EduTrade.user_id == user_id).order_by(EduTrade.id.desc()).limit(30))
    )
    names = strategy_names(s, {t.strategy_id for t in trades if t.strategy_id is not None})
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
                "strategy_id": t.strategy_id,  # None이면 직접 주문
                "strategy_name": None if t.strategy_id is None else names.get(t.strategy_id, "삭제된 전략"),
                "created_at": t.created_at.isoformat(),
            }
            for t in trades
        ],
        "strategy_stats": strategy_stats(s, user_id),
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
