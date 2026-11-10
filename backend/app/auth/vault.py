"""HashiCorp Vault에서 민감정보 읽기·쓰기 (KV v2, 경로 secret/trading)

- JWT 서명 키를 Vault에 보관한다. 없으면 새로 만들어 Vault에 저장한다
  → 백엔드를 다시 띄워도 같은 키를 쓰므로 로그인이 유지되고, 코드·.env에 키가 남지 않는다
- 키움 API 키도 같은 경로에 저장할 예정 (Issue #4)
- Vault에 연결할 수 없으면 환경변수 JWT_SECRET, 그것도 없으면 임시 키를 쓴다 (재시작 시 로그인 풀림)
"""

import logging
import secrets
import time

import httpx

from app.core.config import settings

log = logging.getLogger("uvicorn.error")
PATH = "v1/secret/data/trading"


def _headers() -> dict:
    return {"X-Vault-Token": settings.vault_token}


def read_secrets() -> dict | None:
    """Vault의 secret/trading 값. 연결 실패 시 None, 비어 있으면 {}"""
    try:
        r = httpx.get(f"{settings.vault_addr}/{PATH}", headers=_headers(), timeout=2)
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        return r.json()["data"]["data"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None


def write_secrets(data: dict) -> bool:
    try:
        r = httpx.post(f"{settings.vault_addr}/{PATH}", headers=_headers(), json={"data": data}, timeout=2)
        r.raise_for_status()
        return True
    except httpx.HTTPError:
        return False


def load_jwt_secret(retries: int = 15, delay: float = 1.0) -> tuple[str, str]:
    """(키, 출처) 출처: vault | vault-new | env | temporary

    컨테이너가 동시에 뜰 때 Vault가 늦게 준비될 수 있어서 retries번 재시도한다.
    """
    stored = read_secrets()
    for _ in range(retries - 1):
        if stored is not None:
            break
        log.info("Vault 연결 대기 중...")
        time.sleep(delay)
        stored = read_secrets()
    if stored is not None:
        if stored.get("jwt_secret"):
            return stored["jwt_secret"], "vault"
        new = secrets.token_urlsafe(48)
        if write_secrets({**stored, "jwt_secret": new}):
            return new, "vault-new"
    if settings.jwt_secret:
        return settings.jwt_secret, "env"
    log.warning("Vault 연결 실패, JWT_SECRET도 없음 → 임시 키 사용 (재시작하면 로그인이 풀립니다)")
    return secrets.token_urlsafe(48), "temporary"
