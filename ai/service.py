"""이상거래 탐지 추론 서버 (backend 컨테이너가 http://ai:8001 로 호출)"""

from dataclasses import asdict

from fastapi import FastAPI
from pydantic import BaseModel

from anomaly.rules import Bar, RuleConfig, detect

app = FastAPI(title="Anomaly Detection Service", version="0.1.0")


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
    bars = [Bar(**b.model_dump()) for b in req.bars]
    cfg = RuleConfig(req.window, req.volume_ratio, req.price_change_pct, req.imbalance)
    anomalies = detect(bars, cfg)
    return {"count": len(anomalies), "anomalies": [asdict(a) for a in anomalies]}
