"""이상거래 탐지 서비스 (ai 컨테이너)

- 백그라운드: Kafka 시세를 실시간 검사 (stream.py)
- API: /detect (구간 일괄 검사), /model/status (종목별 모델 학습 상태)
"""

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import asdict

import redis.asyncio as aioredis
from fastapi import FastAPI
from pydantic import BaseModel

import stream
from anomaly.detector import StreamDetector
from anomaly.model import ModelRegistry
from anomaly.rules import Bar, RuleConfig, detect

detector = StreamDetector(ModelRegistry(model_dir=os.getenv("MODEL_DIR", "models")))


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = []
    if os.getenv("ENABLE_STREAM", "true").lower() == "true":
        r = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
        tasks = [asyncio.create_task(stream.run(detector, r)), asyncio.create_task(stream.autosave(detector))]
    yield
    for t in tasks:
        t.cancel()
    detector.registry.save_all()


app = FastAPI(title="Anomaly Detection Service", version="0.2.0", lifespan=lifespan)


class BarIn(BaseModel):
    timestamp: str
    price: float
    volume: float
    bid_size: float = 0.0
    ask_size: float = 0.0


class DetectRequest(BaseModel):
    bars: list[BarIn]
    window: int = 20
    volume_ratio: float = 3.0
    price_change_pct: float = 3.0
    imbalance: float = 0.6


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai"}


@app.post("/detect")
def run_detect(req: DetectRequest):
    """시세 구간을 받아 룰 기반으로 일괄 검사 (타임머신·분석용)"""
    bars = [Bar(**b.model_dump()) for b in req.bars]
    cfg = RuleConfig(req.window, req.volume_ratio, req.price_change_pct, req.imbalance)
    anomalies = detect(bars, cfg)
    return {"count": len(anomalies), "anomalies": [asdict(a) for a in anomalies]}


@app.get("/model/status")
def model_status():
    """종목별 AI 모델 학습 상태 (trained, 수집된 샘플 수)"""
    return detector.registry.status()
