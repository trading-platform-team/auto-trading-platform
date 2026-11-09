import json
import random

import fakeredis
import numpy as np
import pytest

from anomaly.detector import StreamDetector
from anomaly.features import extract
from anomaly.model import ModelRegistry, SymbolModel
from anomaly.rules import Bar, detect, detect_last
from stream import ALERTS_KEY, ANOMALIES_KEY, handle


def _tick(i, price=10000.0, volume=100, bid=500, ask=500, symbol="005930"):
    return {"symbol": symbol, "name": "삼성전자", "price": price, "volume": volume,
            "bid_size": bid, "ask_size": ask, "timestamp": f"t{i:05d}"}


def _normal_stream(n, seed=0):
    rng = random.Random(seed)
    price = 10000.0
    for i in range(n):
        price *= 1 + rng.gauss(0, 0.002)
        yield _tick(i, round(price), rng.randint(80, 120), rng.randint(450, 550), rng.randint(450, 550))


# ---------- 룰 ----------
def test_detect_last_matches_full_scan():
    bars = [Bar(f"t{i}", 10000, 100, 500, 500) for i in range(10)] + [Bar("x", 10600, 900, 500, 500)]
    assert [a.type for a in detect_last(bars)] == [a.type for a in detect(bars) if a.timestamp == "x"]


# ---------- 특징 ----------
def test_extract_features():
    bars = [Bar(f"t{i}", 100, 10, 50, 50) for i in range(5)] + [Bar("x", 103, 50, 90, 10)]
    ret, vol_ratio, imb = extract(bars)
    assert ret == pytest.approx(3.0) and vol_ratio == pytest.approx(5.0) and imb == pytest.approx(0.8)
    assert extract(bars[:2]) is None


# ---------- 모델 ----------
def test_model_trains_after_min_samples_and_flags_outlier():
    rng = np.random.default_rng(0)
    m = SymbolModel(min_samples=100)
    for _ in range(99):
        m.update(rng.normal([0, 1, 0], [0.2, 0.1, 0.05]))
    assert not m.trained
    m.update(np.array([0, 1, 0]))
    assert m.trained

    hit = m.update(np.array([0.0, 8.0, 0.0]))  # 거래량만 8배
    assert hit is not None and hit["cause"] == "vol_ratio"
    assert m.update(np.array([0.0, 1.0, 0.0])) is None  # 평범한 값은 정상


def test_registry_save_and_load(tmp_path):
    reg = ModelRegistry(model_dir=str(tmp_path), min_samples=20)
    rng = np.random.default_rng(1)
    for _ in range(25):
        reg.get("005930").update(rng.normal(size=3))
    assert reg.save_all() == 1

    reloaded = ModelRegistry(model_dir=str(tmp_path))
    assert reloaded.get("005930").trained


# ---------- 실시간 탐지 ----------
def test_stream_detector_normal_then_spike():
    det = StreamDetector(ModelRegistry(min_samples=100))
    alerts = [det.process(t) for t in _normal_stream(300)]
    false_alarms = sum(a is not None for a in alerts[150:])  # 학습 후 정상 구간
    assert false_alarms <= 6  # contamination 1% 수준 (150건 중 소수)

    alert = det.process(_tick(999, price=10000, volume=2000, bid=4000, ask=500))
    assert alert is not None
    methods = {r["method"] for r in alert["reasons"]}
    assert methods == {"rule", "model"} and alert["level"] == "high"


@pytest.mark.asyncio
async def test_handle_saves_to_redis_and_kafka():
    class FakeProducer:
        def __init__(self):
            self.sent = []

        async def send(self, topic, value, key=None):
            self.sent.append((topic, key, value))

    r = fakeredis.FakeAsyncRedis(decode_responses=True)
    det, prod = StreamDetector(ModelRegistry()), FakeProducer()
    for i in range(5):
        assert await handle(det, _tick(i), r, prod) is None
    alert = await handle(det, _tick(5, price=11000), r, prod)  # +10% 급변

    assert alert["reasons"][0]["type"] == "price_jump"
    assert json.loads((await r.lrange(ANOMALIES_KEY, 0, -1))[0])["symbol"] == "005930"
    assert len(await r.lrange(ALERTS_KEY, 0, -1)) == 1
    assert prod.sent[0][0] == "stock.anomaly"


def test_evaluate_lof_beats_isolation_forest():
    from evaluate import main

    r = main(n=2500, seed=3, train=800)
    assert r["LOF (채택)"]["recall"] >= 0.9
    assert r["LOF (채택)"]["f1"] > r["Isolation Forest"]["f1"]
    assert r["LOF (채택)"]["f1"] > r["룰 기반"]["f1"]  # 복합 이상은 룰이 놓침
    assert r["_by_type"]["combo"]["lof"] > r["_by_type"]["combo"]["rule"]


def test_no_alert_echo_after_price_jump():
    """가격 급변 1번 뒤에 같은 종목 경보가 연달아 반복되지 않아야 한다 (학습 100건 기준)"""
    det = StreamDetector(ModelRegistry(min_samples=100))
    stream = list(_normal_stream(400, seed=5))
    for t in stream[:200]:
        det.process(t)
    jump = dict(stream[200], price=stream[199]["price"] * 1.05, timestamp="jump")
    assert det.process(jump) is not None
    after = [det.process(t) for t in stream[201:221]]  # 이후 20건
    assert sum(a is not None for a in after) <= 2
