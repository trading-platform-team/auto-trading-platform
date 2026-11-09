"""실시간 이상탐지기: 룰 기반 + AI 모델(Isolation Forest)을 함께 사용"""

from collections import deque
from datetime import datetime, timezone

from anomaly.features import extract
from anomaly.model import ModelRegistry
from anomaly.rules import Bar, RuleConfig, detect_last

TYPE_KO = {"volume_spike": "거래량 급증", "price_jump": "가격 급변", "orderbook_imbalance": "호가 불균형"}


class StreamDetector:
    def __init__(self, registry: ModelRegistry | None = None, cfg: RuleConfig | None = None, window: int = 300):
        self.registry = registry or ModelRegistry()
        self.cfg = cfg or RuleConfig()
        self.bars: dict[str, deque] = {}
        self.window = window

    def process(self, tick: dict) -> dict | None:
        """시세 1건 처리. 이상 징후가 있으면 경보 dict, 없으면 None"""
        symbol = tick["symbol"]
        bars = self.bars.setdefault(symbol, deque(maxlen=self.window))
        bars.append(
            Bar(tick["timestamp"], tick["price"], tick["volume"], tick.get("bid_size", 0), tick.get("ask_size", 0))
        )
        bar_list = list(bars)

        rule_hits = detect_last(bar_list, self.cfg)
        model_hit = None
        x = extract(bar_list)
        if x is not None:
            model_hit = self.registry.get(symbol).update(x)

        if not rule_hits and not model_hit:
            return None

        reasons = [{"method": "rule", "type": a.type, "value": a.value, "message": a.message} for a in rule_hits]
        if model_hit:
            reasons.append({"method": "model", "type": model_hit["cause"], "value": model_hit["score"],
                            "message": model_hit["message"]})

        # 룰과 모델이 동시에 잡으면 신뢰도 높음
        level = "high" if rule_hits and model_hit else "medium"
        title = ", ".join(TYPE_KO.get(a.type, a.type) for a in rule_hits) or "AI 이상 패턴"
        return {
            "type": "anomaly",
            "level": level,
            "symbol": symbol,
            "name": tick.get("name", symbol),
            "price": tick["price"],
            "message": f"[이상거래] {tick.get('name', symbol)} {title}",
            "reasons": reasons,
            "tick_time": tick["timestamp"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
