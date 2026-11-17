"""주문 실행기 (Broker) - 자체 모의 체결(account="paper") 전략용

자동매매 엔진(engine.py)은 account="paper" 전략을 이 인터페이스로 주문한다.
새 모의 주문 방식은 Broker를 상속해 place()만 구현하면 된다.

- PaperBroker: 전략 주인의 가상계좌로 현재가에 즉시 체결 (잔고 확인, DB orders 테이블에 기록)
- PaperBroker.close(): 익절·손절 매도 (이 전략이 산 수량만)
- 키움 실주문(account="kiwoom")은 app/trading/broker.py 가 따로 맡는다
  (비동기, 위험 제한, kiwoom_orders 테이블). 상태 이름은 그쪽과 같게 맞춘다.

place() 약속
1. 주문 결과를 Order로 DB에 남기고 그 Order를 돌려준다. 거부된 주문도 기록한다.
2. status는 아래 셋 중 하나다.
   - FILLED    체결됨 (PaperBroker는 잔고가 충분하면 즉시 체결)
   - SUBMITTED 접수됨, 체결 대기 (체결이 나중에 확정될 때)
   - REJECTED  거부됨 (잔고·보유 수량 부족 등)
3. 거부 사유는 reason["reject_reason"]에 사람이 읽을 문장으로 넣는다.
4. 주문을 기록하지 못할 만큼 큰 오류(DB 장애 등)만 예외로 올린다.
"""

from abc import ABC, abstractmethod

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.edu import account
from app.edu.models import EduPosition, EduTrade
from app.strategy.models import Order, Strategy

FILLED = "FILLED"
SUBMITTED = "SUBMITTED"
REJECTED = "REJECTED"
ORDER_STATUSES = (FILLED, SUBMITTED, REJECTED)


class Broker(ABC):
    """주문 실행기 공통 인터페이스"""

    name: str = "base"

    @abstractmethod
    def place(self, session: Session, strategy: Strategy, price: float, reason: dict) -> Order:
        """전략의 주문(종목·방향·수량)을 price 기준으로 실행하고 기록된 Order를 돌려준다."""

    @staticmethod
    def record(
        session: Session,
        strategy: Strategy,
        price: float,
        reason: dict,
        status: str,
        reject_reason: str = "",
        side: str | None = None,
        quantity: int | None = None,
    ) -> Order:
        """구현체가 같이 쓰는 주문 기록 함수. side·quantity를 안 주면 전략 설정을 쓴다."""
        if status not in ORDER_STATUSES:
            raise ValueError(f"알 수 없는 주문 상태: {status}")
        if status == REJECTED:
            reason = {**reason, "reject_reason": reject_reason or "주문이 거부되었습니다"}
        order = Order(
            user_id=strategy.user_id,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            symbol=strategy.symbol,
            side=side or strategy.side,
            quantity=quantity or strategy.quantity,
            price=price,
            status=status,
            reason=reason,
        )
        session.add(order)
        session.commit()
        session.refresh(order)
        return order


class PaperBroker(Broker):
    """모의 주문: 전략 주인의 가상계좌(edu/account.py)로 현재가에 즉시 체결

    - 현금이 부족하거나 보유 수량이 부족하면 계좌를 바꾸지 않고 REJECTED로 기록
    - 체결되면 가상계좌 거래(EduTrade, strategy_id 포함)와 주문 내역(Order)을 한 번에 커밋
    """

    name = "paper"

    def place(self, session: Session, strategy: Strategy, price: float, reason: dict) -> Order:
        if strategy.user_id is None:
            return self.record(
                session, strategy, price, reason, REJECTED, "전략 주인이 없어 가상계좌로 주문할 수 없어요"
            )
        try:
            trade = account.place_order(
                session,
                strategy.user_id,
                strategy.symbol,
                strategy.side,
                strategy.quantity,
                price,
                strategy_id=strategy.id,
                commit=False,
            )
        except account.OrderRejected as e:
            session.rollback()
            return self.record(session, strategy, price, reason, REJECTED, str(e))
        return self.record(session, strategy, price, {**reason, "trade_id": trade.id}, FILLED)

    # ---------- 익절·손절 ----------
    @staticmethod
    def held_by_strategy(session: Session, strategy: Strategy) -> int:
        """이 전략이 사서 아직 남아 있는 수량 (직접 주문으로 판 경우 계좌 보유 수량까지만)"""
        signed = case((EduTrade.side == "buy", EduTrade.quantity), else_=-EduTrade.quantity)
        net = session.scalar(
            select(func.coalesce(func.sum(signed), 0)).where(
                EduTrade.user_id == strategy.user_id, EduTrade.strategy_id == strategy.id
            )
        )
        pos = position(session, strategy)
        return max(0, min(int(net or 0), pos.quantity if pos else 0))

    def close(self, session: Session, strategy: Strategy, price: float, quantity: int, reason: dict) -> Order:
        """이 전략이 산 수량을 매도 (익절·손절)"""
        try:
            trade = account.place_order(
                session,
                strategy.user_id,
                strategy.symbol,
                "sell",
                quantity,
                price,
                strategy_id=strategy.id,
                commit=False,
            )
        except account.OrderRejected as e:
            session.rollback()
            return self.record(session, strategy, price, reason, REJECTED, str(e), side="sell", quantity=quantity)
        return self.record(
            session, strategy, price, {**reason, "trade_id": trade.id}, FILLED, side="sell", quantity=quantity
        )


def position(session: Session, strategy: Strategy) -> EduPosition | None:
    return session.scalar(
        select(EduPosition).where(EduPosition.user_id == strategy.user_id, EduPosition.symbol == strategy.symbol)
    )


def exit_reason(strategy: Strategy, avg_price: float, price: float) -> dict | None:
    """익절·손절 조건 확인 (백테스트와 같은 기준: 평균 단가 대비 등락률, 수수료 제외)"""
    if avg_price <= 0:
        return None
    change = (price / avg_price - 1) * 100
    if strategy.take_profit_pct is not None and change >= strategy.take_profit_pct:
        kind, label = "take_profit", "익절"
    elif strategy.stop_loss_pct is not None and change <= -strategy.stop_loss_pct:
        kind, label = "stop_loss", "손절"
    else:
        return None
    return {"exit": kind, "exit_label": label, "change_pct": round(change, 2), "avg_price": round(avg_price, 2)}
