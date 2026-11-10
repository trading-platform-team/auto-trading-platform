"""주문 실행기

- PaperBroker: 현재가로 즉시 체결되는 모의 주문 (DB에 기록)
- KiwoomBroker: 키움 모의투자 주문 API (TODO: Issue #14 후속, 키 발급 후)
"""

from sqlalchemy.orm import Session

from app.strategy.models import Order, Strategy


class PaperBroker:
    def place(self, session: Session, strategy: Strategy, price: float, reason: dict) -> Order:
        order = Order(
            user_id=strategy.user_id,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            symbol=strategy.symbol,
            side=strategy.side,
            quantity=strategy.quantity,
            price=price,
            status="FILLED",
            reason=reason,
        )
        session.add(order)
        session.commit()
        session.refresh(order)
        return order
