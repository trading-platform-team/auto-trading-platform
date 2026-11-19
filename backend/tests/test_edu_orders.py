"""가상계좌 호가창 · 지정가 주문 · 미체결 체결"""

import pytest
from fastapi.testclient import TestClient

from app import db
from app.edu import account, orderbook
from app.history.public_data import PublicStockClient
from app.main import app
from tests.conftest import login


# ---------- 호가 단위 · 호가창 ----------
@pytest.mark.parametrize(
    ("price", "tick"),
    [(1_999, 1), (2_000, 5), (19_990, 10), (20_000, 50), (199_900, 100), (200_000, 500), (500_000, 1_000)],
)
def test_tick_size(price, tick):
    assert orderbook.tick_size(price) == tick


def test_step_and_valid_price():
    assert orderbook.step(4_995, 1) == 5_000 and orderbook.step(5_000, -1) == 4_995
    assert orderbook.step(70_000, 2) == 70_200 and orderbook.step(50_000, -1) == 49_950
    assert orderbook.is_valid_price(70_100) and not orderbook.is_valid_price(70_050)
    assert orderbook.align(70_050) == 70_000


def test_observed_tick_follows_real_prices():
    # 실제 한국투자 분봉에 나온 가격: 표(50원·100원)보다 촘촘하다
    assert orderbook.observed_tick([31_850, 31_875, 31_900]) == 25
    assert orderbook.observed_tick([192_300, 192_400, 192_450]) == 50
    assert orderbook.observed_tick([70_000, 71_000]) == 100  # 표보다 크게 나오면 표 값
    assert orderbook.observed_tick([]) is None
    assert orderbook.is_valid_price(31_875, 25) and not orderbook.is_valid_price(31_875)
    book = orderbook.build("035720", {"price": 31_875, "volume": 10}, tick=25)
    assert book["tick"] == 25 and book["bids"][0]["price"] == 31_850 and book["asks"][-1]["price"] == 31_875


def test_build_is_stable_and_ordered():
    quote = {"price": 70_000, "volume": 1_000, "timestamp": "2026-11-18T10:00:00", "source": "kis_replay"}
    book = orderbook.build("005930", quote)
    assert book == orderbook.build("005930", quote)  # 같은 분봉이면 같은 호가
    asks = [a["price"] for a in book["asks"]]
    bids = [b["price"] for b in book["bids"]]
    assert len(asks) == len(bids) == orderbook.LEVELS
    assert asks[-1] == 70_000 and bids[0] == 69_900  # 매도 1호가 = 현재가
    assert asks == sorted(asks, reverse=True) and bids == sorted(bids, reverse=True)
    assert all(a["quantity"] > 0 for a in book["asks"] + book["bids"])


# ---------- 지정가 · 미체결 ----------
def test_marketable_limit_fills_at_market_price(sqlite_db):
    with db.new_session() as s:
        trade, pending = account.place_limit_order(s, 1, "005930", "buy", 2, 71_000, market_price=70_000)
        assert pending is None and trade.price == 70_000  # 더 비싸게 낼 필요 없이 현재가로 체결


def test_limit_buy_reserves_cash_and_fills_when_touched(sqlite_db):
    with db.new_session() as s:
        _, o = account.place_limit_order(s, 1, "005930", "buy", 10, 69_000, market_price=70_000)
        snap = account.snapshot(s, 1, {})
        assert len(snap["open_orders"]) == 1 and snap["cash"] == account.INITIAL_CASH
        assert snap["available_cash"] == account.INITIAL_CASH - account.buy_cost(69_000, 10)

        # 묶인 현금은 다른 주문에 못 쓴다
        with pytest.raises(account.OrderRejected, match="미체결"):
            account.place_order(s, 1, "000660", "buy", 1, account.INITIAL_CASH - 100_000)

        assert account.match_open_orders(s, {"005930": {"price": 69_500, "low": 69_200}}) == []
        filled = account.match_open_orders(s, {"005930": {"price": 69_500, "low": 68_900}})
        assert len(filled) == 1 and filled[0].price == 69_000  # 저가가 닿으면 지정가로 체결
        snap = account.snapshot(s, 1, {})
        assert snap["open_orders"] == [] and snap["positions"][0]["quantity"] == 10
        assert snap["available_cash"] == snap["cash"]


def test_limit_sell_locks_quantity(sqlite_db):
    with db.new_session() as s:
        account.place_order(s, 1, "005930", "buy", 5, 70_000)
        account.place_limit_order(s, 1, "005930", "sell", 3, 72_000, market_price=70_000)
        assert account.snapshot(s, 1, {})["positions"][0]["sellable"] == 2
        with pytest.raises(account.OrderRejected, match="2주 팔 수"):
            account.place_order(s, 1, "005930", "sell", 3, 70_000)
        with pytest.raises(account.OrderRejected, match="2주 팔 수"):
            account.place_limit_order(s, 1, "005930", "sell", 3, 73_000, market_price=70_000)

        filled = account.match_open_orders(s, {"005930": {"price": 71_800, "high": 72_000}})
        assert filled[0].price == 72_000 and filled[0].realized_pnl > 0
        assert account.snapshot(s, 1, {})["positions"][0]["quantity"] == 2


def test_limit_validation_cancel_and_reset(sqlite_db):
    with db.new_session() as s:
        with pytest.raises(account.OrderRejected, match="호가 단위"):
            account.place_limit_order(s, 1, "005930", "buy", 1, 70_050, market_price=70_000)
        _, ok = account.place_limit_order(s, 1, "005930", "buy", 1, 69_950, market_price=70_000, tick=50)
        account.cancel_order(s, 1, ok.id)
        _, o = account.place_limit_order(s, 1, "005930", "buy", 1, 69_000, market_price=70_000)
        with pytest.raises(account.OrderRejected):
            account.cancel_order(s, 2, o.id)  # 다른 사람 주문
        account.cancel_order(s, 1, o.id)
        assert account.open_orders(s, 1) == []

        account.place_limit_order(s, 1, "005930", "buy", 1, 69_000, market_price=70_000)
        account.reset(s, 1)
        assert account.open_orders(s, 1) == []


# ---------- API ----------
@pytest.fixture
def client(sqlite_db, fake_redis, monkeypatch):
    monkeypatch.setattr("app.main.settings.enable_consumer", False)
    monkeypatch.setattr("app.main.settings.public_data_service_key", "test-key")
    monkeypatch.setattr("app.main.aioredis.from_url", lambda *a, **k: fake_redis)
    price = {"now": 79_600}

    async def latest(self, symbol, end=None):
        return {"symbol": symbol, "price": price["now"], "price_date": "2024-01-02", "source": "public_data"}

    monkeypatch.setattr(PublicStockClient, "latest", latest)
    with TestClient(app) as c:
        c.price = price
        yield c


def test_limit_order_api(client):
    login(client)
    book = client.get("/edu/orderbook/005930").json()
    assert book["price"] == 79_600 and book["tick"] == 100 and book["simulated"]
    assert client.get("/edu/orderbook/999999").status_code == 404

    no_price = {"symbol": "005930", "side": "buy", "quantity": 1, "order_type": "limit"}
    bad = client.post("/edu/account/orders", json=no_price)
    assert bad.status_code == 422
    r = client.post(
        "/edu/account/orders",
        json={"symbol": "005930", "side": "buy", "quantity": 3, "order_type": "limit", "price": 79_000},
    ).json()
    assert r["status"] == "open" and r["price"] == 79_000
    assert r["account"]["open_orders"][0]["quantity"] == 3

    client.price["now"] = 78_900  # 가격이 내려와 지정가에 닿음 → 계좌를 열면 체결
    acc = client.get("/edu/account").json()
    assert acc["open_orders"] == [] and acc["positions"][0]["quantity"] == 3
    assert acc["trades"][0]["price"] == 79_000

    r = client.post(
        "/edu/account/orders",
        json={"symbol": "005930", "side": "sell", "quantity": 1, "order_type": "limit", "price": 80_000},
    ).json()
    assert r["status"] == "open"
    acc = client.delete(f"/edu/account/orders/{r['open_order_id']}").json()
    assert acc["open_orders"] == []
    assert client.delete(f"/edu/account/orders/{r['open_order_id']}").status_code == 404


def test_account_names_come_from_master_when_quote_has_none(client, monkeypatch):
    async def replay(self, symbol):
        return {"symbol": symbol, "price": 79_600, "source": "kis_replay"}  # 한국투자 재생 시세: 이름 없음

    monkeypatch.setattr("app.history.kis_minutes.KisMinuteClient.replay_quote", replay)
    login(client)
    client.post("/edu/account/orders", json={"symbol": "005930", "side": "buy", "quantity": 1})
    r = client.post(
        "/edu/account/orders",
        json={"symbol": "005930", "side": "sell", "quantity": 1, "order_type": "limit", "price": 80_000},
    ).json()
    assert r["account"]["positions"][0]["name"] == "삼성전자"
    assert r["account"]["open_orders"][0]["name"] == "삼성전자"
