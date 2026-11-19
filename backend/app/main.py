import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.api import auth, edu, health, market, stocks, strategies, timemachine, trading, ws
from app.auth import security, vault
from app.core.config import settings
from app.history.kis_minutes import KisMinuteClient
from app.history.public_data import PublicStockClient
from app.kiwoom import platform
from app.kiwoom.watch import publish_strategy_symbols_forever
from app.market.consumer import consume_forever
from app.stocks.service import StockService
from app.trading.executions import ExecutionWatcher

log = logging.getLogger("uvicorn.error")


def _seed_history() -> None:
    """과거 시세가 비어 있으면 가상 일봉을 채운다 (공공데이터 키가 없을 때 타임머신용)"""
    from app.history.service import ensure_seeded

    with db.new_session() as s:
        ensure_seeded(s)


async def _sync_default_history(public: PublicStockClient) -> None:
    """공공데이터 키가 있으면 기본 종목의 가상 일봉을 금융위원회 실제 일봉으로 미리 바꿔 둔다 (타임머신용)"""
    from datetime import date

    from app.history.public_data import PublicDataError
    from app.history.service import SEED_START, sync_public_bars
    from app.market.sources import DEFAULT_SYMBOLS

    for symbol in DEFAULT_SYMBOLS:
        with db.new_session() as s:
            try:
                n = await sync_public_bars(s, public, symbol, SEED_START, date.today())
                log.info("타임머신 실제 일봉 %s: %d개", symbol, n)
            except (PublicDataError, OSError, ValueError) as e:
                s.rollback()
                log.warning("타임머신 실제 일봉 %s 실패, 가상 일봉 유지: %s", symbol, e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    if db.engine is None:  # 테스트에서는 미리 SQLite로 설정해 둔다
        db.configure(settings.database_url)
    await asyncio.to_thread(db.init_db)
    await asyncio.to_thread(_seed_history)
    if security._secret is None:  # 테스트에서는 미리 설정
        secret, source = await asyncio.to_thread(vault.load_jwt_secret)
        security.set_secret(secret)
        log.info("JWT 서명 키 출처: %s", source)
    app.state.public_stocks = PublicStockClient(settings.public_data_service_key, settings.public_data_stock_url)
    kiwoom = platform.open_team_client()  # 키움은 실거래 화면에서만 사용
    app.state.stocks = StockService(app.state.redis, public=app.state.public_stocks)
    app.state.real_stocks = StockService(app.state.redis, kiwoom)
    app.state.kis_minutes = KisMinuteClient(
        settings.kis_app_key,
        settings.kis_app_secret,
        settings.kis_base_url,
        settings.kis_replay_interval_sec,
        redis=app.state.redis,
    )
    app.state.stocks.replay = app.state.kis_minutes  # 재생 중인 종목은 목록에도 같은 가격
    app.state.stocks.warm()  # 종목 목록을 미리 받기 시작
    app.state.real_stocks.warm()
    log.info("가상계좌 연습 시세: %s", "키움 REST API" if kiwoom.enabled else "가상 시세 (키움 키 없음)")
    tasks = [asyncio.create_task(consume_forever(app.state.redis))] if settings.enable_consumer else []
    if settings.kiwoom_execution_ws:  # 실거래 체결 즉시 반영·알림
        tasks.append(asyncio.create_task(ExecutionWatcher(app.state.redis).run_forever()))
    tasks.append(asyncio.create_task(edu.match_forever(app.state, settings.kis_replay_interval_sec)))  # 지정가 체결
    if app.state.public_stocks.enabled:
        tasks.append(asyncio.create_task(_sync_default_history(app.state.public_stocks)))
    if settings.market_source == "kiwoom":
        tasks.append(asyncio.create_task(publish_strategy_symbols_forever(app.state.redis)))  # 실시간 구독할 전략 종목
    yield
    for task in tasks:
        task.cancel()
    await platform.close_team_client()
    await app.state.public_stocks.close()
    await app.state.kis_minutes.close()
    await app.state.redis.aclose()


app = FastAPI(title="보조지표 기반 지능형 자동매매 플랫폼 API", version="0.6.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(edu.router)
app.include_router(health.router)
app.include_router(market.router)
app.include_router(stocks.router)
app.include_router(strategies.router)
app.include_router(timemachine.router)
app.include_router(trading.router)
app.include_router(ws.router)
