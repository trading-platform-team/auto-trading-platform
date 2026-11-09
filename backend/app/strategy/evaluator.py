"""전략 조건 평가: 모든 조건이 참(AND)이면 주문 신호"""

import operator

import numpy as np

from app.strategy.indicators import compute, label

_CMP = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}


def _series(side, closes: np.ndarray) -> np.ndarray:
    if isinstance(side, (int, float)):
        return np.full(len(closes), float(side))
    return compute(side["name"], closes, side.get("period"), side.get("k"))


def evaluate_condition(cond: dict, closes: np.ndarray) -> tuple[bool, dict]:
    left = _series(cond["left"], closes)
    right = _series(cond["right"], closes)
    op = cond["op"]
    right_label = cond["right"] if isinstance(cond["right"], (int, float)) else label(cond["right"])
    detail = {"left": label(cond["left"]), "op": op, "right": right_label}

    if len(closes) < 2 or np.isnan(left[-1]) or np.isnan(right[-1]):
        return False, {**detail, "reason": "데이터 부족"}

    detail.update(left_value=round(float(left[-1]), 2), right_value=round(float(right[-1]), 2))

    if op in _CMP:
        return bool(_CMP[op](left[-1], right[-1])), detail

    if np.isnan(left[-2]) or np.isnan(right[-2]):
        return False, {**detail, "reason": "데이터 부족"}
    if op == "cross_up":
        return bool(left[-2] <= right[-2] and left[-1] > right[-1]), detail
    if op == "cross_down":
        return bool(left[-2] >= right[-2] and left[-1] < right[-1]), detail
    raise ValueError(f"지원하지 않는 연산자: {op}")


def evaluate(conditions: list[dict], closes) -> tuple[bool, list[dict]]:
    closes = np.asarray(closes, dtype=float)
    results = [evaluate_condition(c, closes) for c in conditions]
    return all(ok for ok, _ in results), [d for _, d in results]
