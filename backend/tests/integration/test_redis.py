"""Against a real Redis at REDIS_URL: CI starts one, locally compose.dev.yaml does."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from candlestack.core import Settings, create_redis
from candlestack.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def test_health_with_redis_up(redis_url: str) -> None:
    app = create_app(Settings(app_env="test", app_version="1.2.3", redis_url=redis_url))

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["redis"] == "ok"


def test_health_with_redis_unreachable() -> None:
    app = create_app(Settings(app_env="test", redis_url="redis://127.0.0.1:1/0"))

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "env": "test",
        "version": "dev",
        "commit": "unknown",
        "redis": "error",
    }


@pytest.mark.anyio
async def test_client_keeps_values_as_bytes(redis_url: str) -> None:
    redis = create_redis(redis_url)
    key = f"test:{uuid.uuid4().hex}"
    blob = bytes(range(256))
    try:
        await redis.set(key, blob, ex=60)
        assert await redis.get(key) == blob
    finally:
        await redis.delete(key)
        await redis.aclose()
