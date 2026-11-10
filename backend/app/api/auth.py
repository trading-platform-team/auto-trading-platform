from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.strategies import SessionDep
from app.auth.deps import CurrentUser
from app.auth.models import User
from app.auth.security import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=100)


class LoginIn(BaseModel):
    username: str
    password: str


def _token_response(user: User) -> dict:
    return {"access_token": create_token(user.id, user.username), "token_type": "bearer", "username": user.username}


@router.post("/register", status_code=201)
def register(body: Credentials, s: SessionDep):
    user = User(username=body.username, password_hash=hash_password(body.password))
    s.add(user)
    try:
        s.commit()
    except IntegrityError as e:
        s.rollback()
        raise HTTPException(409, "이미 사용 중인 아이디입니다") from e
    s.refresh(user)
    return _token_response(user)


@router.post("/login")
def login(body: LoginIn, s: SessionDep):
    user = s.scalar(select(User).where(User.username == body.username))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다")
    return _token_response(user)


@router.get("/me")
def me(user: CurrentUser):
    return user
