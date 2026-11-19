"""키움 호가(ka10004) → 화면 호가창"""

import pytest

from app.kiwoom import orderbook


def _sample():
    data = {"bid_req_base_tm": "101500", "tot_sel_req": "+12000", "tot_buy_req": "9000"}
    for n in range(1, 11):
        prefix = "fpr" if n == 1 else f"{n}th_pre"
        data[f"sel_{prefix}_bid"] = f"-{72000 + (n - 1) * 100}"  # 부호는 전일 대비 방향
        data[f"sel_{prefix}_req"] = str(100 * n)
        data[f"buy_{prefix}_bid"] = f"-{71900 - (n - 1) * 100}"
        data[f"buy_{prefix}_req"] = str(50 * n)
    return data


def test_build_orders_levels_and_tick():
    book = orderbook.build("005930", _sample())
    assert book["price"] == 72_000 and book["tick"] == 100 and not book["simulated"]
    assert book["asks"][-1] == {"price": 72_000, "quantity": 100}  # 매도 1호가가 맨 아래
    assert book["asks"][0]["price"] == 72_900 and book["bids"][0] == {"price": 71_900, "quantity": 50}
    assert book["total_ask"] == 12_000 and book["total_bid"] == 9_000


def test_build_skips_missing_levels_and_rejects_empty():
    data = {k: v for k, v in _sample().items() if "10th" not in k}
    assert len(orderbook.build("005930", data)["asks"]) == 9
    with pytest.raises(ValueError):
        orderbook.build("005930", {"sel_fpr_bid": "0"})


def test_orderbook_api_needs_kiwoom_key(fake_redis, sqlite_db, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr("app.main.settings.enable_consumer", False)
    monkeypatch.setattr("app.main.aioredis.from_url", lambda *a, **k: fake_redis)
    with TestClient(app) as c:
        r = c.get("/market/orderbook/005930")
        assert r.status_code == 503 and "키움 키" in r.json()["detail"]
