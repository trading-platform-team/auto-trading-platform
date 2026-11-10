"""타임머신 트레이딩 세션 (직접 매매 모드)

과거 특정 날짜로 돌아가 그날까지의 차트만 보면서 하루씩(또는 자동 재생으로) 시간을 진행하고,
직접 매수·매도한다. 미래 시세는 서버가 보내지 않으므로 '미리 보기'가 불가능하다.
종료하면 같은 기간의 단순 보유, 대표 전략 백테스트와 성과를 비교한다.

세션 상태는 dict로 관리하고 API 계층에서 Redis에 저장한다.
"""

import uuid
from datetime import datetime, timezone

from app.backtest.engine import max_drawdown_pct, run_backtest, summarize
from app.backtest.presets import PRESETS
from app.strategy.indicators import chart_series, clean

WARMUP = 60  # 시작일 이전에 필요한 일봉 수 (지표 계산용)
VISIBLE = 120  # 화면에 보여줄 과거 일봉 수
FEE_PCT = 0.015


class SessionError(ValueError):
    pass


def create(bars: list[dict], symbol: str, name: str, start_date: str, initial_cash: float) -> dict:
    idx = next((i for i, b in enumerate(bars) if b["date"] >= start_date), None)
    if idx is None or idx < WARMUP or idx > len(bars) - 20:
        raise SessionError(f"시작일은 {bars[WARMUP]['date']} ~ {bars[-20]['date']} 사이여야 합니다")
    return {
        "id": uuid.uuid4().hex[:12],
        "symbol": symbol,
        "name": name,
        "start_index": idx,
        "cursor": idx,
        "initial_cash": float(initial_cash),
        "cash": float(initial_cash),
        "qty": 0,
        "avg_price": 0.0,
        "trades": [],
        "equity": [{"date": bars[idx]["date"], "equity": float(initial_cash)}],
        "finished": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _equity(st: dict, price: float) -> float:
    return st["cash"] + st["qty"] * price


def view(st: dict, bars: list[dict]) -> dict:
    """현재 날짜까지의 차트와 계좌 상태 (미래 데이터 없음)"""
    cur = st["cursor"]
    past = bars[: cur + 1]
    series = chart_series([b["close"] for b in past])
    lo = max(0, cur + 1 - VISIBLE)
    chart = [
        {
            "date": b["date"],
            "open": b["open"],
            "high": b["high"],
            "low": b["low"],
            "close": b["close"],
            "volume": b["volume"],
            **{k: clean(v[i]) for k, v in series.items()},
        }
        for i, b in enumerate(past)
        if i >= lo
    ]
    price = bars[cur]["close"]
    equity = _equity(st, price)
    return {
        "id": st["id"],
        "symbol": st["symbol"],
        "name": st["name"],
        "source": bars[cur].get("source", "synthetic"),
        "date": bars[cur]["date"],
        "start_date": bars[st["start_index"]]["date"],
        "days_passed": cur - st["start_index"],
        "days_left": len(bars) - 1 - cur,
        "price": price,
        "chart": chart,
        "account": {
            "cash": round(st["cash"]),
            "qty": st["qty"],
            "avg_price": round(st["avg_price"]),
            "equity": round(equity),
            "return_pct": round((equity / st["initial_cash"] - 1) * 100, 2),
            "unrealized_pct": round((price / st["avg_price"] - 1) * 100, 2) if st["qty"] else None,
        },
        "trades": st["trades"],
        "finished": st["finished"],
    }


def step(st: dict, bars: list[dict], days: int = 1) -> dict:
    if st["finished"]:
        raise SessionError("이미 종료된 세션입니다")
    for _ in range(max(1, min(days, 60))):
        if st["cursor"] >= len(bars) - 1:
            break
        st["cursor"] += 1
        b = bars[st["cursor"]]
        st["equity"].append({"date": b["date"], "equity": _equity(st, b["close"])})
    return st


def order(st: dict, bars: list[dict], side: str, qty: int) -> dict:
    if st["finished"]:
        raise SessionError("이미 종료된 세션입니다")
    price = bars[st["cursor"]]["close"]
    fee = FEE_PCT / 100
    if qty <= 0:
        raise SessionError("수량은 1 이상이어야 합니다")
    if side == "buy":
        cost = qty * price * (1 + fee)
        if cost > st["cash"]:
            raise SessionError(f"현금이 부족합니다 (최대 {int(st['cash'] // (price * (1 + fee)))}주)")
        st["avg_price"] = (st["avg_price"] * st["qty"] + price * qty) / (st["qty"] + qty)
        st["cash"] -= cost
        st["qty"] += qty
        pnl = None
    elif side == "sell":
        if qty > st["qty"]:
            raise SessionError(f"보유 수량이 부족합니다 (보유 {st['qty']}주)")
        st["cash"] += qty * price * (1 - fee)
        pnl = round((price * (1 - fee) / (st["avg_price"] * (1 + fee)) - 1) * 100, 2)
        st["qty"] -= qty
        if st["qty"] == 0:
            st["avg_price"] = 0.0
    else:
        raise SessionError("side는 buy 또는 sell")
    st["trades"].append(
        {"date": bars[st["cursor"]]["date"], "side": side, "quantity": qty, "price": price, "return_pct": pnl}
    )
    st["equity"][-1]["equity"] = _equity(st, price)
    return st


def finish(st: dict, bars: list[dict]) -> dict:
    """종료: 내 성과 vs 단순 보유 vs 대표 전략"""
    st["finished"] = True
    s, e = st["start_index"], st["cursor"]
    period = bars[s : e + 1]
    first, last = bars[s]["close"], bars[e]["close"]
    trades = [{"return_pct": t["return_pct"]} for t in st["trades"] if t["side"] == "sell"]
    mine = summarize(st["initial_cash"], [p["equity"] for p in st["equity"]], trades, first, last)

    compare = [
        {
            "name": "나의 매매",
            "return_pct": mine["total_return_pct"],
            "max_drawdown_pct": mine["max_drawdown_pct"],
            "trades": len(st["trades"]),
            "me": True,
        },
        {
            "name": "단순 보유 (시작일 매수)",
            "return_pct": mine["buy_and_hold_pct"],
            "max_drawdown_pct": max_drawdown_pct([b["close"] for b in period]),
            "trades": 1,
        },
    ]
    if e - s >= 5:
        for p in PRESETS:
            r = run_backtest(
                bars[: e + 1],
                p["buy_conditions"],
                p["sell_conditions"],
                start_index=s,
                initial_cash=st["initial_cash"],
                fee_pct=FEE_PCT,
            )["metrics"]
            compare.append(
                {
                    "name": p["name"],
                    "return_pct": r["total_return_pct"],
                    "max_drawdown_pct": r["max_drawdown_pct"],
                    "trades": r["trades"],
                }
            )
    compare.sort(key=lambda x: x["return_pct"], reverse=True)

    return {
        "period": {"start": period[0]["date"], "end": period[-1]["date"], "days": len(period)},
        "metrics": mine,
        "ranking": compare,
        "equity": [
            {
                "date": p["date"],
                "equity": round(p["equity"]),
                "buy_and_hold": round(st["initial_cash"] * b["close"] / first),
            }
            for p, b in zip(st["equity"], period, strict=False)
        ],
    }
