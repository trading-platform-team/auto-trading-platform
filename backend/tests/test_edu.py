import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import db
from app.edu import account, progress
from app.edu.curriculum import ORDER, UNITS
from app.main import app
from app.market.cache import save_tick
from app.market.sources import make_tick
from tests.conftest import login


# ---------- 진도 로직 ----------
def test_stars():
    assert progress.stars_for(8, 8) == 3
    assert progress.stars_for(6, 8) == 2
    assert progress.stars_for(3, 8) == 1


def test_level_info():
    assert progress.level_info(0) == {"level": 1, "xp_in_level": 0, "xp_for_next": 50}
    assert progress.level_info(130)["level"] == 3


def test_unlock_order_and_xp(sqlite_db):
    with db.new_session() as s:
        with pytest.raises(progress.LessonLocked):
            progress.complete_lesson(s, 1, "u1-l2", 5, 5)  # 1-1을 안 했으면 잠김
        r = progress.complete_lesson(s, 1, "u1-l1", 5, 5)
        assert r["first_time"] and r["xp_gained"] == 15 and r["stars"] == 3
        assert set(r["new_badges"]) == {"first_lesson", "perfect"}

        again = progress.complete_lesson(s, 1, "u1-l1", 3, 5)  # 복습: 절반 XP, 별점은 최고 기록 유지
        assert again["xp_gained"] == 5 and not again["first_time"]
        lesson = again["units"][0]["lessons"][0]
        assert lesson["stars"] == 3 and again["units"][0]["lessons"][1]["unlocked"]
        with pytest.raises(KeyError):
            progress.complete_lesson(s, 1, "u9-l9", 5, 5)  # 없는 레슨


def test_streak(sqlite_db):
    with db.new_session() as s:
        for i, d in enumerate([date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 3)]):
            progress.complete_lesson(s, 1, ORDER[i], 4, 4, day=d)
        p = s.get(progress.EduProgress, 1)
        assert p.streak == 3 and p.best_streak == 3
        progress.complete_lesson(s, 1, ORDER[3], 4, 4, day=date(2026, 11, 5))  # 하루 건너뜀
        assert p.streak == 1 and p.best_streak == 3
        assert "streak_3" in progress.badges(s, 1)


def test_unit_badge(sqlite_db):
    with db.new_session() as s:
        for lid in [x["id"] for x in UNITS[0]["lessons"]]:
            r = progress.complete_lesson(s, 1, lid, 2, 4)
        assert "unit_u1" in r["new_badges"]


# ---------- 교육용 계좌 ----------
def test_account_orders(sqlite_db):
    with db.new_session() as s:
        acc = account.get_or_create(s, 1)
        assert acc.cash == account.INITIAL_CASH
        with pytest.raises(account.OrderRejected, match="최대"):
            account.place_order(s, 1, "005930", "buy", 1000, 70000)  # 7천만 원 > 1천만 원
        with pytest.raises(account.OrderRejected, match="보유 수량"):
            account.place_order(s, 1, "005930", "sell", 1, 70000)

        account.place_order(s, 1, "005930", "buy", 10, 70000)
        account.place_order(s, 1, "005930", "buy", 10, 72000)
        snap = account.snapshot(s, 1, {"005930": {"name": "삼성전자", "price": 75000}})
        pos = snap["positions"][0]
        assert pos["quantity"] == 20 and pos["avg_price"] == 71000  # 평균 단가
        assert pos["return_pct"] == pytest.approx(5.63, abs=0.01)

        t = account.place_order(s, 1, "005930", "sell", 20, 75000)
        buy_fee = 71000 * 20 * account.FEE_PCT / 100  # 평균 단가 기준 매수 수수료
        assert t.realized_pnl == round(4000 * 20 - t.fee - buy_fee)
        snap = account.snapshot(s, 1, {})
        assert snap["positions"] == [] and snap["realized_pnl"] > 0
        assert set(progress.badges(s, 1)) >= {"first_trade", "first_profit"}

        account.reset(s, 1)
        snap = account.snapshot(s, 1, {})
        assert snap["cash"] == account.INITIAL_CASH and snap["trades"] == []


def test_realized_pnl_includes_both_fees(sqlite_db):
    """사자마자 같은 가격에 팔면 실현손익은 매수·매도 수수료만큼 손해이고, 현금 감소액과 같아야 한다"""
    with db.new_session() as s:
        account.place_order(s, 1, "005930", "buy", 10, 70000)
        t = account.place_order(s, 1, "005930", "sell", 10, 70000)
        fees = 2 * round(70000 * 10 * account.FEE_PCT / 100)
        assert t.realized_pnl == -fees
        assert account.get_or_create(s, 1).cash - account.INITIAL_CASH == pytest.approx(t.realized_pnl, abs=1)


def test_realized_pnl_partial_sell(sqlite_db):
    """나눠 팔면 판 수량만큼의 매수 수수료만 빠진다"""
    with db.new_session() as s:
        account.place_order(s, 1, "005930", "buy", 10, 70000)
        first = account.place_order(s, 1, "005930", "sell", 4, 72000)
        second = account.place_order(s, 1, "005930", "sell", 6, 72000)
        assert first.realized_pnl == account.realized_pnl(70000, 72000, 4, first.fee)
        total = first.realized_pnl + second.realized_pnl
        assert account.get_or_create(s, 1).cash - account.INITIAL_CASH == pytest.approx(total, abs=1)


# ---------- API ----------
@pytest.fixture
def client(sqlite_db, fake_redis, monkeypatch):
    monkeypatch.setattr("app.main.settings.enable_consumer", False)
    monkeypatch.setattr("app.main.aioredis.from_url", lambda *a, **k: fake_redis)
    with TestClient(app) as c:
        yield c


def test_edu_api(client, fake_redis):
    assert client.get("/edu/progress").status_code == 401
    login(client)
    prog = client.get("/edu/progress").json()
    assert prog["xp"] == 0 and prog["units"][0]["lessons"][0]["unlocked"]
    assert not prog["units"][0]["lessons"][1]["unlocked"]

    assert client.post("/edu/lessons/u1-l2/complete", json={"correct": 3, "total": 3}).status_code == 409
    r = client.post("/edu/lessons/u1-l1/complete", json={"correct": 3, "total": 3}).json()
    assert r["xp"] == 15 and r["streak"] == 1
    assert client.post("/edu/lessons/u1-l1/complete", json={"correct": 9, "total": 3}).status_code == 422
    assert client.post("/edu/lessons/zzz/complete", json={"correct": 1, "total": 1}).status_code == 404

    asyncio.run(save_tick(fake_redis, make_tick("005930", "삼성전자", 70000, 100, 500, 500)))
    acc = client.get("/edu/account").json()
    assert acc["cash"] == account.INITIAL_CASH
    res = client.post("/edu/account/orders", json={"symbol": "005930", "side": "buy", "quantity": 10}).json()
    assert res["account"]["positions"][0]["quantity"] == 10 and res["badges"] == ["first_trade"]
    bad = client.post("/edu/account/orders", json={"symbol": "005930", "side": "sell", "quantity": 99})
    assert bad.status_code == 422 and "보유 수량" in bad.json()["detail"]
    assert client.post("/edu/account/reset").json()["positions"] == []


# ---------- 직접 주문 / 자동매매 구분, 전략별 통계 ----------
def _make_strategy(s, name="RSI 매수") -> int:
    from app.strategy.models import Strategy

    st = Strategy(user_id=1, name=name, symbol="005930", side="buy", conditions=[], quantity=1)
    s.add(st)
    s.commit()
    return st.id


def test_trades_show_source_and_strategy_stats(sqlite_db):
    with db.new_session() as s:
        sid = _make_strategy(s)
        account.place_order(s, 1, "005930", "buy", 10, 70000)  # 직접
        account.place_order(s, 1, "005930", "buy", 5, 70000, strategy_id=sid)
        account.place_order(s, 1, "005930", "sell", 2, 80000, strategy_id=sid)  # 수익
        account.place_order(s, 1, "005930", "sell", 2, 60000, strategy_id=sid)  # 손실
        account.place_order(s, 1, "005930", "sell", 1, 90000)  # 직접, 수익

        snap = account.snapshot(s, 1, {})
        latest, auto = snap["trades"][0], snap["trades"][1]
        assert latest["strategy_id"] is None and latest["strategy_name"] is None
        assert auto["strategy_id"] == sid and auto["strategy_name"] == "RSI 매수"

        manual, rsi = snap["strategy_stats"]  # 직접 주문이 맨 앞
        assert manual == {
            "strategy_id": None, "name": "직접 주문", "auto": False, "trades": 2, "buys": 1, "sells": 1,
            "wins": 1, "realized_pnl": manual["realized_pnl"], "win_rate": 100.0,
        }
        assert rsi["name"] == "RSI 매수" and rsi["auto"] is True
        assert (rsi["trades"], rsi["buys"], rsi["sells"], rsi["wins"], rsi["win_rate"]) == (3, 1, 2, 1, 50.0)
        assert manual["realized_pnl"] + rsi["realized_pnl"] == snap["realized_pnl"]


def test_stats_keep_deleted_strategy_and_empty(sqlite_db):
    from app.strategy.models import Strategy

    with db.new_session() as s:
        assert account.snapshot(s, 1, {})["strategy_stats"] == []
        sid = _make_strategy(s)
        account.place_order(s, 1, "005930", "buy", 1, 70000, strategy_id=sid)
        s.delete(s.get(Strategy, sid))
        s.commit()
        snap = account.snapshot(s, 1, {})
        assert snap["trades"][0]["strategy_name"] == "삭제된 전략"
        (row,) = snap["strategy_stats"]
        assert row["name"] == "삭제된 전략" and row["win_rate"] is None  # 매도 없음


def test_reset_clears_paper_orders_but_keeps_strategies(sqlite_db):
    """초기화하면 자동매매 모의 주문 내역도 지운다 (전략과 다른 사용자 주문은 그대로)"""
    from app.strategy.broker import PaperBroker
    from app.strategy.models import Order, Strategy

    with db.new_session() as s:
        sid = _make_strategy(s)
        PaperBroker().place(s, s.get(Strategy, sid), 70000, {})
        s.add(Order(user_id=2, strategy_name="남의 전략", symbol="005930", side="buy", quantity=1, price=1))
        s.commit()

        account.reset(s, 1)
        assert s.query(Order).filter_by(user_id=1).count() == 0
        assert s.query(Order).filter_by(user_id=2).count() == 1
        assert s.get(Strategy, sid) is not None
        assert account.snapshot(s, 1, {})["strategy_stats"] == []
