"""대표 전략 (백테스트 프리셋, 타임머신 결과 비교용)"""

PRESETS = [
    {
        "id": "golden_cross",
        "name": "골든크로스 / 데드크로스",
        "description": "5일선이 20일선을 상향 돌파하면 매수, 하향 돌파하면 매도",
        "buy_conditions": [
            {"left": {"name": "SMA", "period": 5}, "op": "cross_up", "right": {"name": "SMA", "period": 20}}
        ],
        "sell_conditions": [
            {"left": {"name": "SMA", "period": 5}, "op": "cross_down", "right": {"name": "SMA", "period": 20}}
        ],
    },
    {
        "id": "rsi_reversal",
        "name": "RSI 역추세",
        "description": "RSI(14)가 30 아래면 매수, 70 위면 매도",
        "buy_conditions": [{"left": {"name": "RSI", "period": 14}, "op": "<", "right": 30}],
        "sell_conditions": [{"left": {"name": "RSI", "period": 14}, "op": ">", "right": 70}],
    },
    {
        "id": "bollinger_rebound",
        "name": "볼린저밴드 반등",
        "description": "종가가 하단 밴드 아래면 매수, 중간선 위로 올라오면 매도",
        "buy_conditions": [{"left": {"name": "PRICE"}, "op": "<", "right": {"name": "BB_LOWER", "period": 20}}],
        "sell_conditions": [{"left": {"name": "PRICE"}, "op": ">", "right": {"name": "BB_MIDDLE", "period": 20}}],
    },
]
