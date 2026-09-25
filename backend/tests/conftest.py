"""Fixtures shared by the unit and integration tests.

``app`` is ``create_app(settings)`` with Redis replaced by ``fake_redis``; ``client`` runs it
(lifespan included) in a TestClient. Tests override ``settings`` or ``fake_redis`` to vary them.
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from candlestack.core import Settings
from candlestack.core.redis import get_redis
from candlestack.main import create_app


class FakeRedis:
    """Stands in for the Redis client where a test only needs it up or down."""

    def __init__(self, *, up: bool = True) -> None:
        self.up = up

    async def ping(self) -> bool:
        if not self.up:
            raise RedisConnectionError("Connection refused")
        return True


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    return Settings(app_env="test", app_version="1.2.3", app_commit="abc1234")


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def app(settings: Settings, fake_redis: FakeRedis) -> FastAPI:
    app = create_app(settings)
    app.dependency_overrides[get_redis] = lambda: fake_redis
    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
