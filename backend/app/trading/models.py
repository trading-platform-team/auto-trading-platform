from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class KiwoomSetting(Base):
    """사용자별 실거래 설정. 서버나 한도를 바꾸면 다시 활성화해야 한다."""

    __tablename__ = "kiwoom_settings"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    env: Mapped[str] = mapped_column(String(4), default="mock")  # mock | real
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    max_order_amount: Mapped[int] = mapped_column(Integer, default=1_000_000)  # 1회 주문 한도 (원)
    daily_loss_limit: Mapped[int] = mapped_column(Integer, default=100_000)  # 하루 손실 한도 (원)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class KiwoomOrder(Base):
    """키움으로 보낸 주문 (또는 위험 제한으로 막힌 주문)

    status: SUBMITTED 접수 / PARTIAL 일부 체결 / FILLED 체결 / REJECTED 키움 거부 / BLOCKED 위험 제한
    """

    __tablename__ = "kiwoom_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    strategy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strategy_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    env: Mapped[str] = mapped_column(String(4))
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[int] = mapped_column(Integer)
    order_type: Mapped[str] = mapped_column(String(6), default="market")  # market | limit
    price: Mapped[float] = mapped_column(Float)  # 지정가, 시장가면 주문 당시 시세
    ord_no: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="SUBMITTED")
    filled_qty: Mapped[int] = mapped_column(Integer, default=0)
    filled_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(String(300), default="")
    reason: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
