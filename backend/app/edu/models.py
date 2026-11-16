"""교육 페이지 테이블: 학습 진도, 레슨 결과, 교육용 가상계좌

교육용 가상계좌는 모의투자 페이지(팀원 2)의 가상계좌와 별개다.
"""

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EduProgress(Base):
    __tablename__ = "edu_progress"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_study_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class EduLessonResult(Base):
    __tablename__ = "edu_lesson_results"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_edu_lesson"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    lesson_id: Mapped[str] = mapped_column(String(20))
    stars: Mapped[int] = mapped_column(Integer)  # 1~3 (가장 좋았던 기록)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EduAccount(Base):
    __tablename__ = "edu_accounts"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    initial_cash: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EduPosition(Base):
    __tablename__ = "edu_positions"
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_edu_position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer)
    avg_price: Mapped[float] = mapped_column(Float)


class EduTrade(Base):
    __tablename__ = "edu_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String(20))
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)  # 매도 시 실현손익
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
