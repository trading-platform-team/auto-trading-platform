"""이상탐지 모델 비교 평가

합성 시세(정답 라벨 포함)로 룰 기반과 AI 모델 3종을 비교한다.
앞 1000건으로 학습, 나머지로 평가.

실행: python evaluate.py
"""

import argparse
import warnings

import numpy as np
from sklearn.covariance import EllipticEnvelope
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

from anomaly.features import extract
from anomaly.model import SymbolModel
from anomaly.rules import detect_last
from anomaly.synthetic import generate

warnings.filterwarnings("ignore")
LOF_THRESHOLD = SymbolModel().threshold
KIND_KO = {"volume": "거래량 급증", "price": "가격 급변", "orderbook": "호가 불균형", "combo": "복합(룰 미달)"}


def build_dataset(n: int, seed: int, with_kinds: bool = False):
    bars, X, y, rule, kinds = [], [], [], [], []
    for bar, label, kind in generate(n, seed=seed):
        bars.append(bar)
        f = extract(bars[-300:])
        if f is None:
            continue
        X.append(f)
        y.append(label)
        rule.append(int(bool(detect_last(bars[-300:]))))
        kinds.append(kind)
    if with_kinds:
        return np.array(X), np.array(y), np.array(rule), np.array(kinds)
    return np.array(X), np.array(y), np.array(rule)


def metrics(y_true, y_pred) -> dict:
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "false_alarms": fp}


def main(n: int = 4000, seed: int = 1, train: int = 1000, verbose: bool = True) -> dict:
    X, y, rule, kinds = build_dataset(n, seed, with_kinds=True)
    scaler = StandardScaler().fit(X[:train])
    Xtr, Xte, yte = scaler.transform(X[:train]), scaler.transform(X[train:]), y[train:]

    models = {
        "Isolation Forest": IsolationForest(contamination=0.02, random_state=0),
        "Elliptic Envelope": EllipticEnvelope(contamination=0.02, random_state=0),
    }
    results = {"룰 기반": metrics(yte, rule[train:])}
    for name, m in models.items():
        m.fit(Xtr)
        results[name] = metrics(yte, (m.predict(Xte) == -1).astype(int))

    lof = LocalOutlierFactor(n_neighbors=20, novelty=True).fit(Xtr)  # 실제 서비스와 같은 설정
    lof_pred = (-lof.score_samples(Xte) > LOF_THRESHOLD).astype(int)
    results["LOF (채택)"] = metrics(yte, lof_pred)

    # 이상 종류별 탐지율 (룰 vs LOF)
    kte, rte = kinds[train:], rule[train:]
    results["_by_type"] = {
        k: {"count": int((m := kte == k).sum()), "rule": float(rte[m].mean()), "lof": float(lof_pred[m].mean())}
        for k in ("volume", "price", "orderbook", "combo") if (kte == k).any()
    }

    if not verbose:
        return results
    print(f"평가 데이터 {len(yte)}건 (이상 {int(yte.sum())}건)\n")
    print(f"{'모델':<20}{'Precision':>10}{'Recall':>10}{'F1':>8}{'오탐':>6}")
    for name, r in results.items():
        if name.startswith("_"):
            continue
        print(f"{name:<20}{r['precision']:>10.2f}{r['recall']:>10.2f}{r['f1']:>8.2f}{r['false_alarms']:>6}")
    _print_by_type([results])
    return results


def _print_by_type(runs: list[dict]) -> None:
    print(f"\n이상 종류별 탐지율\n{'종류':<12}{'건수':>6}{'룰':>8}{'LOF':>8}")
    for k in ("volume", "price", "orderbook", "combo"):
        rows = [r["_by_type"][k] for r in runs if k in r["_by_type"]]
        if rows:
            cnt = sum(x["count"] for x in rows)
            rule = sum(x["rule"] * x["count"] for x in rows) / cnt
            lof = sum(x["lof"] * x["count"] for x in rows) / cnt
            print(f"{KIND_KO[k]:<12}{cnt:>6}{rule:>8.2f}{lof:>8.2f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=4000)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--seeds", type=int, default=1, help="여러 seed 평균")
    a = p.parse_args()
    if a.seeds == 1:
        main(a.n, a.seed)
    else:
        runs = [main(a.n, s, verbose=False) for s in range(a.seeds)]
        print(f"seed {a.seeds}개 평균\n")
        print(f"{'모델':<20}{'Precision':>10}{'Recall':>10}{'F1':>8}")
        for name in runs[0]:
            if name.startswith("_"):
                continue
            avg = {k: np.mean([r[name][k] for r in runs]) for k in ("precision", "recall", "f1")}
            print(f"{name:<20}{avg['precision']:>10.2f}{avg['recall']:>10.2f}{avg['f1']:>8.2f}")
        _print_by_type(runs)
