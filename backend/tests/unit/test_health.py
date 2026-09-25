import asyncio

import pytest
from fastapi.testclient import TestClient

from candlestack.core import health


def test_ok_when_redis_answers(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    # Compact JSON: the deploy checks match these substrings.
    assert response.content == (
        b'{"status":"ok","env":"test","version":"1.2.3","commit":"abc1234","redis":"ok"}'
    )


def test_503_when_redis_is_down(client: TestClient, fake_redis) -> None:
    fake_redis.up = False

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "env": "test",
        "version": "1.2.3",
        "commit": "abc1234",
        "redis": "error",
    }


def test_503_when_redis_hangs(
    client: TestClient, fake_redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def hang() -> bool:
        await asyncio.sleep(10)
        return True

    monkeypatch.setattr(fake_redis, "ping", hang)
    monkeypatch.setattr(health, "REDIS_TIMEOUT", 0.05)

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["redis"] == "error"
