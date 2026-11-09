"""LOF(Local Outlier Factor) 기반 이상탐지 모델 (종목별)

- 종목마다 시세 특징을 모아 학습한다 (비지도 학습, 라벨 불필요)
- 특징은 표준화(StandardScaler) 후 사용
- LOF 점수(1 근처면 정상, 클수록 이상)가 threshold를 넘으면 이상으로 판정
- Isolation Forest, Elliptic Envelope와 비교한 결과 LOF가 가장 좋아서 채택 (evaluate.py 참고)
  Isolation Forest는 학습 범위를 벗어난 값(예: 평소의 8배 거래량)을 경계값처럼 취급해 놓치는 경우가 많았다
- min_samples개가 모이면 첫 학습, 이후 refit_every개마다 최근 데이터로 재학습
- 학습된 모델은 models/ 폴더(도커 볼륨)에 저장해서 재시작해도 유지된다
- 이상으로 판정되면 평소 대비 가장 크게 벗어난 특징을 '원인'으로 알려준다
"""

from collections import deque
from pathlib import Path

import joblib
import numpy as np
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

from anomaly.features import FEATURE_KO, FEATURES


class SymbolModel:
    def __init__(self, min_samples: int = 100, refit_every: int = 200, history: int = 2000,
                 threshold: float = 3.0, n_neighbors: int = 20):
        self.min_samples = min_samples
        self.refit_every = refit_every
        self.threshold = threshold
        self.n_neighbors = n_neighbors
        self.buffer: deque = deque(maxlen=history)
        self.model: LocalOutlierFactor | None = None
        self.scaler: StandardScaler | None = None
        self.mean = self.std = None
        self.since_fit = 0

    @property
    def trained(self) -> bool:
        return self.model is not None

    def fit(self) -> None:
        X = np.array(self.buffer)
        self.scaler = StandardScaler().fit(X)
        self.model = LocalOutlierFactor(n_neighbors=self.n_neighbors, novelty=True)
        self.model.fit(self.scaler.transform(X))
        self.mean, self.std = X.mean(axis=0), X.std(axis=0) + 1e-9
        self.since_fit = 0

    def update(self, x: np.ndarray) -> dict | None:
        """특징 1건 추가 + 판정. 이상이면 결과 dict, 아니면 None"""
        result = None
        if self.trained:
            xs = self.scaler.transform([x])
            score = float(-self.model.score_samples(xs)[0])  # LOF 점수: 1 근처 정상, 클수록 이상
            if score > self.threshold:
                z = (x - self.mean) / self.std
                top = int(np.argmax(np.abs(z)))
                cause = FEATURE_KO[FEATURES[top]]
                result = {
                    "score": round(score, 2),
                    "cause": FEATURES[top],
                    "message": f"AI 모델: 평소와 다른 {cause} 패턴 (LOF={score:.1f}, z={z[top]:+.1f})",
                    "features": dict(zip(FEATURES, (round(float(v), 4) for v in x), strict=True)),
                }

        self.buffer.append(x)
        self.since_fit += 1
        if (not self.trained and len(self.buffer) >= self.min_samples) or (
            self.trained and self.since_fit >= self.refit_every
        ):
            self.fit()
        return result


class ModelRegistry:
    """종목별 모델 관리 + 디스크 저장/불러오기"""

    def __init__(self, model_dir: str | None = None, **model_kwargs):
        self.dir = Path(model_dir) if model_dir else None
        self.kwargs = model_kwargs
        self.models: dict[str, SymbolModel] = {}

    def get(self, symbol: str) -> SymbolModel:
        if symbol not in self.models:
            self.models[symbol] = self._load(symbol) or SymbolModel(**self.kwargs)
        return self.models[symbol]

    def _path(self, symbol: str) -> Path:
        return self.dir / f"lof_{symbol}.joblib"

    def _load(self, symbol: str) -> SymbolModel | None:
        if self.dir and self._path(symbol).exists():
            return joblib.load(self._path(symbol))
        return None

    def save_all(self) -> int:
        if not self.dir:
            return 0
        self.dir.mkdir(parents=True, exist_ok=True)
        saved = 0
        for symbol, m in self.models.items():
            if m.trained:
                joblib.dump(m, self._path(symbol))
                saved += 1
        return saved

    def status(self) -> dict:
        return {s: {"trained": m.trained, "samples": len(m.buffer)} for s, m in self.models.items()}
