"""PostgreSQL 연결 (SQLAlchemy). 테스트에서는 SQLite 메모리 DB로 교체한다."""

import logging
import time

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

log = logging.getLogger("uvicorn.error")


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal: sessionmaker | None = None


def configure(url: str) -> None:
    global engine, SessionLocal
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    engine = create_engine(url, pool_pre_ping=True, **kwargs)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db(retries: int = 30, delay: float = 2.0) -> None:
    """테이블 생성. PostgreSQL 컨테이너가 늦게 뜰 수 있어서 재시도한다."""
    from app.auth import models as _a  # noqa: F401 - 테이블 등록
    from app.history import models as _h  # noqa: F401
    from app.strategy import models  # noqa: F401

    for i in range(retries):
        try:
            Base.metadata.create_all(engine)
            _migrate()
            return
        except OperationalError:
            log.info("DB 연결 대기 중... (%d/%d)", i + 1, retries)
            time.sleep(delay)
    raise RuntimeError("DB에 연결할 수 없습니다")


# create_all은 이미 있는 테이블에 컬럼을 추가하지 않으므로, 기존 볼륨(pg-data)을 쓰는 환경을 위해 직접 추가한다
_ADDED_COLUMNS = {"strategies": {"user_id": "INTEGER"}, "orders": {"user_id": "INTEGER"}}


def _migrate() -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in _ADDED_COLUMNS.items():
            existing = {c["name"] for c in insp.get_columns(table)}
            for col, typ in cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
                    log.info("DB 컬럼 추가: %s.%s", table, col)


def get_session():
    with SessionLocal() as session:
        yield session


def new_session() -> Session:
    return SessionLocal()
