"""비밀번호 해시 + JWT 발급·검증

- 비밀번호: PBKDF2-SHA256 (사용자별 salt, 반복 200,000회). 원문은 저장하지 않는다
- 토큰: HS256 JWT, 유효기간 12시간. 서명 키는 Vault에서 가져온다 (app/auth/vault.py)
"""

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

ITERATIONS = 200_000
TOKEN_HOURS = 12
_secret: str | None = None


def set_secret(secret: str) -> None:
    global _secret
    _secret = secret


def _key() -> str:
    if not _secret:
        raise RuntimeError("JWT 서명 키가 설정되지 않았습니다")
    return _secret


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(iterations))
        return hmac.compare_digest(calc, base64.b64decode(digest))
    except ValueError:
        return False


def create_token(user_id: int, username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "name": username, "iat": now, "exp": now + timedelta(hours=TOKEN_HOURS)}
    return jwt.encode(payload, _key(), algorithm="HS256")


def decode_token(token: str) -> dict | None:
    """유효하면 {'id', 'username'}, 아니면 None"""
    try:
        p = jwt.decode(token, _key(), algorithms=["HS256"])
        return {"id": int(p["sub"]), "username": p["name"]}
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
