"""키움 주식호가요청 (ka10004) → 화면용 호가창 (가상계좌 호가창과 같은 모양)

응답은 1호가가 sel_fpr_bid / buy_fpr_bid (최우선), 2~10호가가 sel_{n}th_pre_bid / buy_{n}th_pre_bid 이고
잔량은 같은 이름의 _req 필드다. 가격에는 전일 대비 부호가 붙어 온다 (예: "-72100").
실제 키움 서버 응답으로는 아직 확인하지 못했다 → 필드가 없으면 그 호가는 건너뛴다.
"""

from app.kiwoom import parse

LEVELS = 10
API_ID = "ka10004"
PATH = "/api/dostk/mrkcond"


def _level(data: dict, side: str, n: int) -> dict | None:
    prefix = f"{side}_fpr" if n == 1 else f"{side}_{n}th_pre"
    price = parse.price(data.get(f"{prefix}_bid"))
    if price <= 0:
        return None
    return {"price": price, "quantity": parse.qty(data.get(f"{prefix}_req"))}


def build(symbol: str, data: dict) -> dict:
    asks = [lvl for n in range(1, LEVELS + 1) if (lvl := _level(data, "sel", n))]
    bids = [lvl for n in range(1, LEVELS + 1) if (lvl := _level(data, "buy", n))]
    if not asks and not bids:
        raise ValueError("호가가 비어 있어요 (장 시작 전이거나 거래정지 종목일 수 있어요)")
    prices = sorted({lvl["price"] for lvl in asks + bids})
    gaps = [b - a for a, b in zip(prices, prices[1:], strict=False) if b > a]
    return {
        "symbol": symbol,
        "price": asks[0]["price"] if asks else bids[0]["price"],  # 매도 1호가 (지금 사면 체결되는 가격)
        "tick": min(gaps) if gaps else None,
        "asks": asks[::-1],  # 화면 위쪽이 높은 가격
        "bids": bids,
        "total_ask": parse.qty(data.get("tot_sel_req")) or sum(a["quantity"] for a in asks),
        "total_bid": parse.qty(data.get("tot_buy_req")) or sum(b["quantity"] for b in bids),
        "timestamp": data.get("bid_req_base_tm"),
        "source": "kiwoom",
        "simulated": False,
    }
