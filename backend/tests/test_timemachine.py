from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.backtest.engine import max_drawdown_pct, run_backtest
from app.history.synthetic import generate_daily
from app.main import app
from app.timemachine import session as tm
from tests.conftest import login


def _bars(closes):
    return [{"date": f"2024-01-{i + 1:02d}" if i < 31 else f"2024-02-{i - 30:02d}", "open": c, "high": c, "low": c,
             "close": c, "volume": 1000} for i, c in enumerate(closes)]


# ---------- 가상 일봉 ----------
def test_synthetic_is_deterministic_and_business_days_only():
    a = generate_daily("005930", 70000, date(2024, 1, 1), date(2024, 3, 31))
    b = generate_daily("005930", 70000, date(2024, 1, 1), date(2024, 3, 31))
    assert a == b
    assert all(d["date"].weekday() < 5 for d in a)
    assert all(d["low"] <= min(d["open"], d["close"]) and d["high"] >= max(d["open"], d["close"]) for d in a)


# ---------- 백테스트 엔진 ----------
def test_mdd():
    assert max_drawdown_pct([100, 120, 90, 130]) == -25.0


def test_backtest_buy_low_sell_high():
    closes = [100, 90, 80, 90, 100, 110, 120]
    buy = [{"left": {"name": "PRICE"}, "op": "<=", "right": 80}]
    sell = [{"left": {"name": "PRICE"}, "op": ">=", "right": 120}]
    r = run_backtest(_bars(closes), buy, sell, initial_cash=10_000, fee_pct=0)
    t = r["trades"][0]
    assert (t["entry_price"], t["exit_price"]) == (80, 120)
    assert t["return_pct"] == 50.0
    assert r["metrics"]["total_return_pct"] == 50.0  # 125주 * 80 = 10,000 → 125 * 120 = 15,000
    assert r["metrics"]["buy_and_hold_pct"] == 20.0
    assert [p["side"] for p in r["points"]] == ["buy", "sell"]


def test_backtest_stop_loss_and_open_position():
    closes = [100, 100, 95, 89, 100, 100]
    buy = [{"left": {"name": "PRICE"}, "op": ">=", "right": 100}]
    r = run_backtest(_bars(closes), buy, [], initial_cash=1000, fee_pct=0, stop_loss_pct=10)
    assert r["trades"][0]["exit_reason"].startswith("손절")
    assert r["trades"][-1]["exit_reason"] == "보유 중"  # 다시 매수 후 기간 종료


def test_backtest_does_not_use_future_data():
    """조건 평가에 그날 종가까지만 써야 한다: 마지막 날 가격을 바꿔도 이전 매매는 같아야 함"""
    closes = list(range(100, 140)) + list(range(140, 100, -1))
    buy = [{"left": {"name": "PRICE"}, "op": "cross_down", "right": {"name": "SMA", "period": 5}}]
    sell = [{"left": {"name": "PRICE"}, "op": "cross_up", "right": {"name": "SMA", "period": 5}}]
    a = run_backtest(_bars(closes), buy, sell, start_index=10)["trades"]
    b = run_backtest(_bars(closes[:-1] + [999]), buy, sell, start_index=10)["trades"]
    assert a[: len(a) - 1] == b[: len(a) - 1]


# ---------- 타임머신 세션 ----------
def test_session_flow():
    bars = [{**b, "date": b["date"].isoformat()} for b in generate_daily("005930", 70000, date(2024, 1, 1),
                                                                        date(2024, 12, 31))]
    st = tm.create(bars, "005930", "삼성전자", bars[80]["date"], 10_000_000)
    v = tm.view(st, bars)
    assert v["chart"][-1]["date"] == bars[80]["date"]  # 미래 데이터 없음
    assert len(v["chart"]) == 81 or len(v["chart"]) == tm.VISIBLE

    tm.order(st, bars, "buy", 10)
    with pytest.raises(tm.SessionError):
        tm.order(st, bars, "sell", 11)
    tm.step(st, bars, 20)
    tm.order(st, bars, "sell", 10)
    assert st["qty"] == 0 and st["trades"][-1]["return_pct"] is not None

    result = tm.finish(st, bars)
    names = [r["name"] for r in result["ranking"]]
    assert "나의 매매" in names and "단순 보유 (시작일 매수)" in names and len(names) == 5
    with pytest.raises(tm.SessionError):
        tm.step(st, bars)


def test_session_start_date_validation():
    bars = [{**b, "date": b["date"].isoformat()} for b in generate_daily("005930", 70000, date(2024, 1, 1),
                                                                        date(2024, 6, 30))]
    with pytest.raises(tm.SessionError):
        tm.create(bars, "005930", "삼성전자", bars[10]["date"], 1_000_000)  # 워밍업 부족


# ---------- API ----------
@pytest.fixture
def client(sqlite_db, fake_redis, monkeypatch):
    monkeypatch.setattr("app.main.settings.enable_consumer", False)
    monkeypatch.setattr("app.main.aioredis.from_url", lambda *a, **k: fake_redis)
    monkeypatch.setattr("app.api.timemachine.settings.ai_service_url", "http://127.0.0.1:9")  # AI 없음
    with TestClient(app) as c:
        login(c)
        yield c


def test_history_seeded(client):
    syms = client.get("/history/symbols").json()
    assert len(syms) == 5 and syms[0]["source"] == "synthetic"
    assert len(client.get("/history/005930?start=2024-01-01&end=2024-01-31").json()) == 23


def test_backtest_api(client):
    presets = client.get("/backtest/presets").json()
    body = {"symbol": "005930", "start": "2024-01-02", "end": "2025-06-30",
            "buy_conditions": presets[0]["buy_conditions"], "sell_conditions": presets[0]["sell_conditions"]}
    r = client.post("/backtest", json=body).json()
    assert {"total_return_pct", "buy_and_hold_pct", "max_drawdown_pct", "win_rate_pct"} <= r["metrics"].keys()
    assert r["trades"] and r["chart"][0]["date"] >= "2024-01-02" and r["source"] == "synthetic"

    no_exit = {**body, "sell_conditions": []}
    assert client.post("/backtest", json=no_exit).status_code == 422


def test_timemachine_api(client):
    v = client.post("/timemachine/sessions", json={"symbol": "000660", "start_date": "2024-06-03"}).json()
    sid, start = v["id"], v["date"]
    assert v["chart"][-1]["date"] == start and v["anomalies"] == []

    v = client.post(f"/timemachine/sessions/{sid}/order", json={"side": "buy", "quantity": 5}).json()
    assert v["account"]["qty"] == 5
    assert client.post(f"/timemachine/sessions/{sid}/order", json={"side": "sell", "quantity": 9}).status_code == 422

    v = client.post(f"/timemachine/sessions/{sid}/step", json={"days": 10}).json()
    assert v["date"] > start and v["days_passed"] == 10
    assert all(c["date"] <= v["date"] for c in v["chart"])

    result = client.post(f"/timemachine/sessions/{sid}/finish").json()
    assert result["period"]["days"] == 11 and len(result["ranking"]) == 5
    assert client.post(f"/timemachine/sessions/{sid}/step", json={"days": 1}).status_code == 409
    assert client.get("/timemachine/sessions/nope").status_code == 404
