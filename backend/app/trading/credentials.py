"""사용자 키움 키 조회

키 등록·저장(Vault)은 다른 담당자가 구현한다. 이 모듈은 '사용자 ID와 서버로 키를 꺼내는 함수' 하나만 약속한다.

    get_credentials(user_id: int, env: "mock" | "real") -> KiwoomCredentials | None

키 등록 기능을 만들면 앱 시작 시 set_provider(내_함수)를 호출해 연결한다.
(내_함수는 동기 함수, 키가 없으면 None. 키 원문을 로그에 남기지 않기)

그 전까지는 KIWOOM_DEV_USE_TEAM_KEY=true일 때 모든 사용자가 팀 모의투자 키를 쓴다 (mock 서버만).
"""

from collections.abc import Callable

from app.core.config import settings
from app.kiwoom import platform
from app.kiwoom.client import KiwoomCredentials

Provider = Callable[[int, str], KiwoomCredentials | None]


def _dev_provider(user_id: int, env: str) -> KiwoomCredentials | None:
    if settings.kiwoom_dev_use_team_key and env == "mock" and platform.team_env() == "mock":
        return platform.team_credentials()
    return None


_provider: Provider = _dev_provider


def set_provider(provider: Provider) -> None:
    global _provider
    _provider = provider


def reset_provider() -> None:
    set_provider(_dev_provider)


def get_credentials(user_id: int, env: str) -> KiwoomCredentials | None:
    creds = _provider(user_id, env)
    if creds is not None and creds.env != env:
        raise ValueError("요청한 서버와 키의 서버가 다릅니다")  # 실전/모의 키 혼동 방지
    return creds
