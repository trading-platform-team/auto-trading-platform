"""팀 키움 키 (.env의 KIWOOM_APP_KEY / KIWOOM_SECRET_KEY / KIWOOM_BASE_URL)

- 프로세스마다 KiwoomClient 하나를 같이 쓴다 (가상계좌 연습 StockService, 실시간 시세, 개발용 주문)
  → 토큰 하나, 호출 간격 하나로 호출 제한(429)을 피한다
- 팀 키로 만든 KiwoomClient에는 주문 메서드가 없다. 주문은 KiwoomTradeApi로만 (app/trading/broker.py)
- 사용자 키 등록 기능이 생기기 전까지 KIWOOM_DEV_USE_TEAM_KEY=true면 팀 키로 모의 주문 (app/trading/credentials.py)
"""

import httpx

from app.core.config import settings
from app.kiwoom.client import KiwoomClient, KiwoomCredentials, env_of

_client: KiwoomClient | None = None


def team_env() -> str:
    return env_of(settings.kiwoom_base_url)


def team_credentials() -> KiwoomCredentials | None:
    if not (settings.kiwoom_app_key and settings.kiwoom_secret_key):
        return None
    return KiwoomCredentials(settings.kiwoom_app_key.strip(), settings.kiwoom_secret_key.strip(), team_env())


def open_team_client(transport: httpx.AsyncBaseTransport | None = None) -> KiwoomClient:
    """서버(또는 collector) 시작 시 한 번. 키가 없어도 만들고, enabled로 구분한다"""
    global _client
    per_sec = settings.kiwoom_rest_per_sec
    _client = KiwoomClient(settings.kiwoom_base_url, settings.kiwoom_app_key, settings.kiwoom_secret_key,
                           transport=transport, min_interval=1 / per_sec if per_sec > 0 else 0)
    return _client


def team_client() -> KiwoomClient | None:
    return _client


async def close_team_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def default_symbols() -> list[str]:
    return [s.strip() for s in settings.kiwoom_default_symbols.split(",") if s.strip()]
