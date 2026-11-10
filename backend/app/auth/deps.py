from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.security import decode_token

bearer = HTTPBearer(auto_error=False)
Creds = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def optional_user(creds: Creds) -> dict | None:
    return decode_token(creds.credentials) if creds else None


def current_user(creds: Creds) -> dict:
    user = optional_user(creds)
    if not user:
        raise HTTPException(401, "로그인이 필요합니다", headers={"WWW-Authenticate": "Bearer"})
    return user


CurrentUser = Annotated[dict, Depends(current_user)]
OptionalUser = Annotated[dict | None, Depends(optional_user)]
