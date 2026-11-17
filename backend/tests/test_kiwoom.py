"""키움 연동 테스트 (가짜 키움 서버, 키 없이 실행)"""

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.kiwoom import parse, platform, watch
from app.kiwoom.client import REST_HOSTS, KiwoomClient, KiwoomCredentials, KiwoomError, KiwoomTradeApi
from app.kiwoom.realtime import KiwoomRealtime, TickAggregator
from app.main import app
from app.market.cache import save_tick
from app.market.sources import KiwoomSource, make_tick
from app.stocks.service import StockService
from app.strategy.engine import on_tick
from app.trading import broker, credentials
from tests.conftest import login
from tests.kiwoom_fake import FakeKiwoom, FakeWs

TEAM = KiwoomCredentials("mock-app", "mock-secret", "mock")
USER = KiwoomCredentials("user-app", "user-secret", "mock")


@pytest.fixture
def fake():
    return FakeKiwoom()


def team_client(fake, secret="mock-secret"):
    return KiwoomClient(REST_HOSTS["mock"], "mock-app", secret, transport=fake.transport(), min_interval=0)


def trade_api(fake):
    return KiwoomTradeApi(USER, transport=fake.transport(), min_interval=0)


async def stock_info(client, code="005930"):
    data, _ = await client.call("ka10001", "/api/dostk/stkinfo", {"stk_cd": code})
    return data


# ---------- 값 변환 ----------
def test_parse_signed_strings():
    assert parse.price("+72000") == 72000
    assert parse.price("-70500") == 70500  # 가격 부호는 방향일 뿐
    assert parse.to_num("-1.41") == -1.41
    assert parse.qty("-000150") == 150
    assert parse.to_num("1,234") == 1234
    assert parse.to_num("") == 0 and parse.to_num(None) == 0 and parse.to_num("abc") == 0
    assert parse.code("A005930") == "005930" and parse.code("005930_NX") == "005930"


def test_credentials_hide_key():
    assert "mock-app" not in repr(TEAM) and "mock-secret" not in repr(TEAM)
    with pytest.raises(ValueError):
        KiwoomCredentials("a", "b", "prod")


# ---------- REST 클라이언트 (팀원 KiwoomClient 위에서 동작 확인) ----------
@pytest.mark.asyncio
async def test_token_reused(fake):
    client = team_client(fake)
    await stock_info(client)
    await stock_info(client)
    assert fake.token_count == 1
    assert client.env == "mock" and await client.token() == "tok1"


@pytest.mark.asyncio
async def test_invalid_token_refreshes_once(fake):
    client = team_client(fake)
    await stock_info(client)
    fake.tokens.clear()  # 서버에서 토큰 만료
    info = await stock_info(client)
    assert info["stk_nm"] == "삼성전자" and fake.token_count == 2


@pytest.mark.asyncio
async def test_business_error_raises(fake):
    with pytest.raises(KiwoomError) as e:
        await stock_info(team_client(fake), "999999")
    assert e.value.code == "1902" and e.value.message


@pytest.mark.asyncio
async def test_wrong_key_fails(fake):
    with pytest.raises(KiwoomError):
        await stock_info(team_client(fake, secret="wrong"))


@pytest.mark.asyncio
async def test_call_all_follows_paging(fake):
    rows = await team_client(fake).call_all("ka10099", "/api/dostk/stkinfo", {"mrkt_tp": "0"}, "list")
    assert [r["code"] for r in rows] == ["005930", "000660", "005935"]


def test_team_client_has_no_order_methods():
    assert not hasattr(KiwoomClient, "order") and not hasattr(KiwoomClient, "balance")


@pytest.mark.asyncio
async def test_trade_api_reuses_shared_client(fake):
    client = team_client(fake)
    api = KiwoomTradeApi(TEAM, client=client)
    await api.balance()
    await stock_info(client)
    assert fake.token_count == 1  # 팀 키 토큰 하나를 같이 씀


@pytest.mark.asyncio
async def test_order_body_market_and_limit(fake):
    api = trade_api(fake)
    await api.order("buy", "005930", 3)
    await api.order("sell", "005930", 2, price=75000)
    (id1, b1), (id2, b2) = fake.calls[-2:]
    assert id1 == "kt10000" and b1["trde_tp"] == "3" and b1["ord_uv"] == "" and b1["ord_qty"] == "3"
    assert id2 == "kt10001" and b2["trde_tp"] == "0" and b2["ord_uv"] == "75000"


# ---------- 구독 대상 ----------
@pytest.mark.asyncio
async def test_desired_symbols_priority_and_limit(fake_redis):
    await fake_redis.sadd(watch.STRATEGY_KEY, "000660")
    await watch.touch(fake_redis, "035720")
    await watch.touch(fake_redis, "005380", ttl=-1)  # 이미 만료
    got = await watch.desired_symbols(fake_redis, ["005930"], limit=10)
    assert got == ["000660", "005930", "035720"]
    assert await watch.desired_symbols(fake_redis, ["005930"], limit=2) == ["000660", "005930"]


# ---------- 실시간 ----------
def real(type_, item, values):
    return {"trnm": "REAL", "data": [{"type": type_, "name": "", "item": item, "values": values}]}


@pytest.mark.asyncio
async def test_realtime_login_subscribe_ping():
    ws = FakeWs([
        {"trnm": "LOGIN", "return_code": 0, "return_msg": ""},
        {"trnm": "PING"},
        real("0B", "005930", {"10": "+72000", "15": "+10"}),
    ])

    async def tok():
        return "tok"

    async with KiwoomRealtime("real", tok, connect=ws) as rt:
        await rt.sync(["005930", "000660"])
        await rt.sync(["005930"])
        items = [i async for i in rt.messages()]
    assert ws.url == "wss://api.kiwoom.com:10000/api/dostk/websocket"
    assert ws.sent[0] == {"trnm": "LOGIN", "token": "tok"}
    assert ws.sent[1]["trnm"] == "REG" and ws.sent[1]["data"][0]["item"] == ["005930", "000660"]
    assert ws.sent[2]["trnm"] == "REMOVE" and ws.sent[2]["data"][0]["item"] == ["000660"]
    assert {"trnm": "PING"} in ws.sent  # PING 에코
    assert items[0]["values"]["10"] == "+72000"


@pytest.mark.asyncio
async def test_realtime_login_failure():
    ws = FakeWs([{"trnm": "LOGIN", "return_code": 8005, "return_msg": "토큰 오류"}])

    async def tok():
        return "bad"

    with pytest.raises(KiwoomError):
        async with KiwoomRealtime("real", tok, connect=ws):
            pass


def test_aggregator_sums_volume_and_keeps_book():
    agg = TickAggregator()
    agg.feed({"type": "0D", "item": "005930", "values": {"121": "800", "125": "1200"}})
    agg.feed({"type": "0B", "item": "005930", "values": {"10": "+72000", "15": "+10"}})
    agg.feed({"type": "0B", "item": "005930", "values": {"10": "-71900", "15": "-5"}})
    [tick] = agg.flush(lambda s: "삼성전자")
    assert tick["price"] == 71900 and tick["volume"] == 15
    assert tick["bid_size"] == 1200 and tick["ask_size"] == 800 and tick["name"] == "삼성전자"
    assert agg.flush(lambda s: s) == []  # 새 체결이 없으면 내보내지 않음


@pytest.mark.asyncio
async def test_kiwoom_source_streams_ticks(fake, fake_redis):
    ws = FakeWs([
        {"trnm": "LOGIN", "return_code": 0},
        {"trnm": "REG", "return_code": 0},
        real("0B", "005930", {"10": "+72000", "15": "+7"}),
    ])
    src = KiwoomSource(fake_redis, client=team_client(fake), connect=ws, interval=0.01, defaults=["005930"])
    gen = src.stream()
    ticks = await anext(gen)
    await gen.aclose()
    assert ticks[0]["symbol"] == "005930" and ticks[0]["price"] == 72000 and ticks[0]["name"] == "삼성전자"
    assert ws.sent[1]["trnm"] == "REG"


def test_kiwoom_source_requires_key(fake_redis, monkeypatch):
    monkeypatch.setattr(platform, "_client", None)
    with pytest.raises(RuntimeError, match="KIWOOM_APP_KEY"):
        KiwoomSource(fake_redis)


# ---------- API: 종목 검색·조회 ----------
@pytest.fixture
def client(sqlite_db, fake_redis, fake, monkeypatch):
    monkeypatch.setattr("app.main.settings.enable_consumer", False)
    monkeypatch.setattr("app.main.aioredis.from_url", lambda *a, **k: fake_redis)
    monkeypatch.setattr("app.trading.broker.settings.kiwoom_rest_per_sec", 0)
    monkeypatch.setattr(broker, "transport", fake.transport())
    broker.reset_apis()
    credentials.set_provider(lambda uid, env: USER if env == "mock" else None)
    with TestClient(app) as c:
        login(c)
        yield c
    credentials.reset_provider()
    broker.reset_apis()


def test_quote_from_cache_and_watch(client, fake_redis):
    tick = make_tick("005930", "삼성전자", 70000, 100, 500, 500)
    client.portal.call(save_tick, fake_redis, tick)
    res = client.get("/market/quote/005930")
    assert res.json()["price"] == 70000 and res.json()["source"] == "mock"
    assert "005930" in client.portal.call(fake_redis.zrange, watch.WATCH_KEY, 0, -1)
    assert client.get("/market/quote/999999").status_code == 404
    assert client.get("/market/quote/bad").status_code == 422
    assert client.post("/market/watch/000660").json()["watching"] is True
    assert "000660" in client.portal.call(fake_redis.zrange, watch.WATCH_KEY, 0, -1)


def test_quote_from_kiwoom(client, fake, fake_redis):
    client.app.state.stocks = StockService(fake_redis, team_client(fake))  # 팀원 StockService (ka10095)
    q = client.get("/market/quote/005930").json()
    assert q["price"] == 72000 and q["change_pct"] == 1.41 and q["source"] == "kiwoom" and q["name"] == "삼성전자"
    client.get("/market/quote/005930")
    assert fake.ids().count("ka10095") == 1  # 5초 캐시
    assert client.get("/market/quote/999999").status_code == 404


# ---------- API: 실거래 ----------
def activate(client, env="mock", max_amount=1_000_000, loss=100_000):
    client.put("/trading/kiwoom/settings", json={"env": env, "max_order_amount": max_amount,
                                                 "daily_loss_limit": loss})
    return client.post("/trading/kiwoom/activate", json={"confirm": "모의투자를 시작합니다"})


def test_settings_default_disabled(client):
    st = client.get("/trading/kiwoom/settings").json()
    assert st["enabled"] is False and st["env"] == "mock" and st["confirm_text"] == "모의투자를 시작합니다"


def test_activate_requires_confirm_text(client):
    res = client.post("/trading/kiwoom/activate", json={"confirm": "네"})
    assert res.status_code == 400


def test_real_needs_its_own_confirm_and_key(client):
    client.put("/trading/kiwoom/settings", json={"env": "real", "max_order_amount": 500_000,
                                                 "daily_loss_limit": 50_000})
    assert client.post("/trading/kiwoom/activate", json={"confirm": "모의투자를 시작합니다"}).status_code == 400
    res = client.post("/trading/kiwoom/activate", json={"confirm": "실거래를 시작합니다"})
    assert res.status_code == 400 and "키움 키" in res.json()["detail"]  # 실전 키 미등록


def test_activate_and_settings_change_disables(client):
    res = activate(client)
    assert res.status_code == 200 and res.json()["enabled"] is True
    st = client.put("/trading/kiwoom/settings", json={"env": "mock", "max_order_amount": 2_000_000,
                                                      "daily_loss_limit": 100_000}).json()
    assert st["enabled"] is False


def test_order_blocked_when_disabled(client, fake, fake_redis):
    res = client.post("/trading/kiwoom/orders", json={"symbol": "005930", "side": "buy", "quantity": 1,
                                                      "price": 70000})
    assert res.json()["status"] == "BLOCKED"
    assert not any(a.startswith("kt100") for a in fake.ids())  # 키움에 주문이 나가지 않음


def test_order_over_max_amount_blocked(client, fake):
    activate(client, max_amount=100_000)
    res = client.post("/trading/kiwoom/orders", json={"symbol": "005930", "side": "buy", "quantity": 2,
                                                      "price": 70000}).json()
    assert res["status"] == "BLOCKED" and "1회 주문 한도" in res["message"]
    assert "kt10000" not in fake.ids()


def test_order_submit_sync_and_cancel(client, fake):
    activate(client)
    o = client.post("/trading/kiwoom/orders", json={"symbol": "005930", "side": "buy", "quantity": 10,
                                                    "price": 70000}).json()
    assert o["status"] == "SUBMITTED" and o["ord_no"] == "0000001" and o["order_type"] == "limit"

    fake.fill("0000001", 4, 70000)
    fake.fill("0000001", 6, 70100)
    [synced] = client.get("/trading/kiwoom/orders").json()
    assert synced["status"] == "FILLED" and synced["filled_qty"] == 10 and synced["filled_price"] == 70060

    o2 = client.post("/trading/kiwoom/orders", json={"symbol": "005930", "side": "sell", "quantity": 1,
                                                     "price": 80000}).json()
    res = client.post(f"/trading/kiwoom/orders/{o2['id']}/cancel")
    assert res.json()["status"] == "CANCELLED" and fake.calls[-1][0] == "kt10003"
    assert client.post(f"/trading/kiwoom/orders/{o['id']}/cancel").status_code == 400  # 이미 체결


def test_market_order_needs_price(client, fake_redis):
    activate(client)
    body = {"symbol": "005930", "side": "buy", "quantity": 1}
    assert client.post("/trading/kiwoom/orders", json=body).status_code == 400
    client.portal.call(save_tick, fake_redis, make_tick("005930", "삼성전자", 70000, 100, 500, 500))
    o = client.post("/trading/kiwoom/orders", json=body).json()
    assert o["status"] == "SUBMITTED" and o["order_type"] == "market" and o["price"] == 70000


def test_market_order_uses_kiwoom_quote_without_realtime(client, fake, fake_redis):
    client.app.state.stocks = StockService(fake_redis, team_client(fake))
    activate(client)
    o = client.post("/trading/kiwoom/orders", json={"symbol": "035720", "side": "buy", "quantity": 1}).json()
    assert o["status"] == "SUBMITTED" and o["price"] == 72000  # 실시간 시세가 없어 현재가 조회로 기준가


def test_daily_loss_limit_disables_trading(client, fake):
    activate(client, loss=100_000)
    client.post("/trading/kiwoom/orders", json={"symbol": "005930", "side": "buy", "quantity": 1, "price": 70000})
    fake.assets -= 150_000  # 오늘 15만 원 손실
    o = client.post("/trading/kiwoom/orders", json={"symbol": "005930", "side": "buy", "quantity": 1,
                                                    "price": 70000}).json()
    assert o["status"] == "BLOCKED" and "일일 손실 한도" in o["message"]
    st = client.get("/trading/kiwoom/settings").json()
    assert st["enabled"] is False and "일일 손실" in st["disabled_reason"]


def test_kiwoom_rejection_recorded(client, fake):
    activate(client)
    fake.fail_next["kt10000"] = (200, 20, "주문가능금액이 부족합니다")
    o = client.post("/trading/kiwoom/orders", json={"symbol": "005930", "side": "buy", "quantity": 1,
                                                    "price": 70000}).json()
    assert o["status"] == "REJECTED" and "주문가능금액" in o["message"]


def test_account_summary(client):
    activate(client)
    acc = client.get("/trading/kiwoom/account").json()
    assert acc["summary"]["estimated_assets"] == 10_000_000
    assert acc["holdings"][0] == {
        "symbol": "005930", "name": "삼성전자", "quantity": 14, "sellable": 14, "avg_price": 71428,
        "price": 75000, "eval_amount": 1_050_000, "profit": 50_000, "profit_rate": 5.0,
    }
    assert acc["cash"]["orderable"] == 8_900_000 and acc["today"]["loss"] == 0


def test_deactivate_kill_switch(client):
    activate(client)
    st = client.post("/trading/kiwoom/deactivate").json()
    assert st["enabled"] is False and st["disabled_reason"] == "사용자가 정지했습니다"


def test_other_user_cannot_cancel(client):
    activate(client)
    o = client.post("/trading/kiwoom/orders", json={"symbol": "005930", "side": "buy", "quantity": 1,
                                                    "price": 70000}).json()
    login(client, "otheruser")
    assert client.post(f"/trading/kiwoom/orders/{o['id']}/cancel").status_code == 404
    assert client.get("/trading/kiwoom/orders").json() == []


# ---------- 자동매매 엔진 → 키움 ----------
def test_strategy_with_kiwoom_account_orders_through_broker(client, fake, fake_redis):
    activate(client)
    st = client.post("/strategies", json={
        "name": "실거래 RSI", "symbol": "005930", "side": "buy", "quantity": 2, "cooldown_sec": 0,
        "account": "kiwoom", "conditions": [{"left": {"name": "RSI", "period": 14}, "op": "<", "right": 30}],
    }).json()
    assert st["account"] == "kiwoom"
    for p in np.arange(140, 100, -1, dtype=float):  # 계속 하락 → RSI 0
        client.portal.call(save_tick, fake_redis, make_tick("005930", "삼성전자", p, 100, 500, 500))
    [order] = client.portal.call(on_tick, fake_redis, make_tick("005930", "삼성전자", 100, 100, 500, 500))
    assert order["status"] == "SUBMITTED" and order["strategy_id"] == st["id"]
    assert fake.calls[-1][0] == "kt10000" and fake.calls[-1][1]["trde_tp"] == "3"
    alert = json.loads(client.portal.call(fake_redis.lindex, "alerts", 0))
    assert "키움 주문 접수" in alert["message"]
    assert client.get("/orders").json() == []  # 자체 모의 주문에는 기록되지 않음


@pytest.mark.asyncio
async def test_publish_strategy_symbols(sqlite_db, fake_redis):
    from app import db
    from app.strategy.models import Strategy

    with db.new_session() as s:
        s.add_all([Strategy(name="a", symbol="000660", side="buy", conditions=[], enabled=True),
                   Strategy(name="b", symbol="035720", side="buy", conditions=[], enabled=False)])
        s.commit()
    assert await watch.publish_strategy_symbols(fake_redis) == ["000660"]
    assert await fake_redis.smembers(watch.STRATEGY_KEY) == {"000660"}
