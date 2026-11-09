import socket
from urllib.parse import urlparse

import httpx
import redis
from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


def _tcp_check(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_redis() -> bool:
    try:
        return bool(redis.from_url(settings.redis_url, socket_timeout=1).ping())
    except redis.RedisError:
        return False


def check_kafka() -> bool:
    host, _, port = settings.kafka_bootstrap_servers.split(",")[0].partition(":")
    return _tcp_check(host, int(port or 9092))


def check_postgres() -> bool:
    url = urlparse(settings.database_url)
    return _tcp_check(url.hostname or "localhost", url.port or 5432)


def check_vault() -> bool:
    try:
        r = httpx.get(f"{settings.vault_addr}/v1/sys/health", timeout=1)
        return r.status_code < 500
    except httpx.HTTPError:
        return False


def check_ai() -> bool:
    try:
        return httpx.get(f"{settings.ai_service_url}/health", timeout=1).status_code == 200
    except httpx.HTTPError:
        return False


@router.get("/health")
def health():
    """백엔드 자체 상태"""
    return {"status": "ok", "service": settings.app_name}


@router.get("/health/deps")
def health_deps():
    """다른 컨테이너(Kafka, Redis, PostgreSQL, Vault, AI)와 통신되는지 확인"""
    deps = {
        "kafka": check_kafka(),
        "redis": check_redis(),
        "postgres": check_postgres(),
        "vault": check_vault(),
        "ai": check_ai(),
    }
    return {"status": "ok" if all(deps.values()) else "degraded", "deps": deps}
