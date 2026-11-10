"""백테스트 엔진 (자동 백테스트 모드)

일봉 종가 기준으로 매수 조건 / 매도 조건을 평가해서 가상 매매를 실행한다.
- 롱 전용(보유 or 미보유), 매수 시 현금의 position_pct%를 사용
- 신호가 난 날의 종가로 체결 (조건 계산에 그날 종가까지만 사용 → 미래 데이터 사용 없음)
- 익절(take_profit_pct)·손절(stop_loss_pct)을 선택적으로 사용
- 거래 비용 fee_pct%를 매수·매도 때마다 차감
"""

import numpy as np

from app.strategy.evaluator import evaluate


def max_drawdown_pct(equity: list[float]) -> float:
    peak, mdd = -np.inf, 0.0
    for v in equity:
        peak = max(peak, v)
        mdd = min(mdd, (v - peak) / peak * 100)
    return round(mdd, 2)


def summarize(
    initial_cash: float, equity: list[float], trades: list[dict], first_close: float, last_close: float
) -> dict:
    """성과 지표 (백테스트·타임머신 공용)"""
    closed = [t for t in trades if t.get("return_pct") is not None]
    wins = [t for t in closed if t["return_pct"] > 0]
    final = equity[-1] if equity else initial_cash
    return {
        "initial_cash": initial_cash,
        "final_equity": round(final),
        "total_return_pct": round((final / initial_cash - 1) * 100, 2),
        "buy_and_hold_pct": round((last_close / first_close - 1) * 100, 2),
        "max_drawdown_pct": max_drawdown_pct(equity),
        "trades": len(closed),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "avg_trade_return_pct": round(float(np.mean([t["return_pct"] for t in closed])), 2) if closed else None,
    }


def run_backtest(
    bars: list[dict],
    buy_conditions: list[dict],
    sell_conditions: list[dict] | None = None,
    start_index: int = 0,
    initial_cash: float = 10_000_000,
    position_pct: float = 100,
    fee_pct: float = 0.015,
    take_profit_pct: float | None = None,
    stop_loss_pct: float | None = None,
) -> dict:
    """bars[start_index:] 구간을 시뮬레이션. 앞부분(start_index 이전)은 지표 계산용 워밍업."""
    closes = np.array([b["close"] for b in bars], dtype=float)
    fee = fee_pct / 100
    cash, qty, entry = float(initial_cash), 0, None
    equity, trades, points = [], [], []

    for i in range(start_index, len(bars)):
        price, day = closes[i], bars[i]["date"]
        window = closes[: i + 1]

        if qty == 0:
            ok, details = evaluate(buy_conditions, window)
            if ok:
                n = int(cash * position_pct / 100 // (price * (1 + fee)))
                if n > 0:
                    cash -= n * price * (1 + fee)
                    qty, entry = n, {"date": day, "price": price, "reason": details}
                    points.append({"date": day, "side": "buy", "price": price})
        else:
            change = (price / entry["price"] - 1) * 100
            reason = None
            if take_profit_pct is not None and change >= take_profit_pct:
                reason = f"익절 {change:+.2f}%"
            elif stop_loss_pct is not None and change <= -stop_loss_pct:
                reason = f"손절 {change:+.2f}%"
            elif sell_conditions and evaluate(sell_conditions, window)[0]:
                reason = "매도 조건 충족"
            if reason:
                cash += qty * price * (1 - fee)
                ret = (price * (1 - fee)) / (entry["price"] * (1 + fee)) * 100 - 100
                trades.append(
                    {
                        "entry_date": entry["date"],
                        "entry_price": entry["price"],
                        "exit_date": day,
                        "exit_price": price,
                        "quantity": qty,
                        "return_pct": round(ret, 2),
                        "exit_reason": reason,
                    }
                )
                points.append({"date": day, "side": "sell", "price": price})
                qty, entry = 0, None

        equity.append(cash + qty * price)

    if entry:  # 기간 종료 시 보유 중인 포지션은 평가만 (미청산)
        trades.append(
            {
                "entry_date": entry["date"],
                "entry_price": entry["price"],
                "exit_date": None,
                "exit_price": None,
                "quantity": qty,
                "return_pct": None,
                "exit_reason": "보유 중",
            }
        )

    period = bars[start_index:]
    first, last = closes[start_index], closes[-1]
    return {
        "metrics": summarize(initial_cash, equity, trades, first, last),
        "equity": [
            {"date": b["date"], "equity": round(e), "buy_and_hold": round(initial_cash * c / first)}
            for b, e, c in zip(period, equity, closes[start_index:], strict=True)
        ],
        "trades": trades,
        "points": points,
    }
