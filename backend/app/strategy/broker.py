"""주문 실행기 (Broker)

자동매매 엔진(engine.py)은 어떤 Broker를 쓰든 같은 방식으로 주문한다.
새 주문 방식은 Broker를 상속해 place()만 구현하면 된다.

- PaperBroker: 현재가로 즉시 체결되는 모의 주문 (DB에 기록)
- KiwoomBroker: 키움 REST API 주문 (팀원 3, 같은 인터페이스로 구현 예정)

place() 약속
1. 주문 결과를 Order로 DB에 남기고 그 Order를 돌려준다. 거부된 주문도 기록한다.
2. status는 아래 셋 중 하나다.
   - FILLED   체결됨 (PaperBroker는 항상 즉시 체결)
   - PENDING  접수됨, 체결 대기 (실제 증권사 주문처럼 체결이 나중에 확정될 때)
   - REJECTED 거부됨 (잔고·보유 수량 부족, 위험 한도 초과, 증권사 거부 등)
3. 거부 사유는 reason["reject_reason"]에 사람이 읽을 문장으로 넣는다.
4. 주문을 기록하지 못할 만큼 큰 오류(DB 장애 등)만 예외로 올린다.
"""

from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from app.strategy.models import Order, Strategy

FILLED = "FILLED"
PENDING = "PENDING"
REJECTED = "REJECTED"
ORDER_STATUSES = (FILLED, PENDING, REJECTED)


class Broker(ABC):
    """주문 실행기 공통 인터페이스"""

    name: str = "base"

    @abstractmethod
    def place(self, session: Session, strategy: Strategy, price: float, reason: dict) -> Order:
        """전략의 주문(종목·방향·수량)을 price 기준으로 실행하고 기록된 Order를 돌려준다."""

    @staticmethod
    def record(
        session: Session, strategy: Strategy, price: float, reason: dict, status: str, reject_reason: str = ""
    ) -> Order:
        """구현체가 같이 쓰는 주문 기록 함수"""
        if status not in ORDER_STATUSES:
            raise ValueError(f"알 수 없는 주문 상태: {status}")
        if status == REJECTED:
            reason = {**reason, "reject_reason": reject_reason or "주문이 거부되었습니다"}
        order = Order(
            user_id=strategy.user_id,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            symbol=strategy.symbol,
            side=strategy.side,
            quantity=strategy.quantity,
            price=price,
            status=status,
            reason=reason,
        )
        session.add(order)
        session.commit()
        session.refresh(order)
        return order


class PaperBroker(Broker):
    """모의 주문: 현재가로 즉시 체결 (잔고 확인은 가상계좌 연결 단계에서 추가)"""

    name = "paper"

    def place(self, session: Session, strategy: Strategy, price: float, reason: dict) -> Order:
        return self.record(session, strategy, price, reason, FILLED)
