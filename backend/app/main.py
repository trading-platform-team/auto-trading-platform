import asyncio
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.api import health, market, strategies, timemachine, ws
from app.core.config import settings
from app.market.consumer import consume_forever


def _seed_history() -> None:
    """과거 시세가 비어 있으면 가상 일봉을 채운다 (키움 연동 전 타임머신용)"""
    from app.history.service import ensure_seeded

    with db.new_session() as s:
        ensure_seeded(s)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    if db.engine is None:  # 테스트에서는 미리 SQLite로 설정해 둔다
        db.configure(settings.database_url)
    await asyncio.to_thread(db.init_db)
    await asyncio.to_thread(_seed_history)
    task = asyncio.create_task(consume_forever(app.state.redis)) if settings.enable_consumer else None
    yield
    if task:
        task.cancel()
    await app.state.redis.aclose()


app = FastAPI(title="보조지표 기반 지능형 자동매매 플랫폼 API", version="0.5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(market.router)
app.include_router(strategies.router)
app.include_router(timemachine.router)
app.include_router(ws.router)
