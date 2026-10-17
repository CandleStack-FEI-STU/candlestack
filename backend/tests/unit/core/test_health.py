import asyncio

import pytest
from fastapi.testclient import TestClient

from candlestack.core import health


def test_ok_when_redis_and_postgres_answer(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    # Compact JSON: the deploy checks match these substrings.
    assert response.content == (
        b'{"status":"ok","env":"test","version":"1.2.3","commit":"abc1234","redis":"ok",'
        b'"postgres":"ok"}'
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
        "postgres": "ok",
    }


def test_503_when_postgres_is_down(client: TestClient, fake_database) -> None:
    fake_database.up = False

    response = client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert (body["status"], body["redis"], body["postgres"]) == ("error", "ok", "error")


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


def test_503_when_postgres_hangs(
    client: TestClient, fake_database, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def hang() -> None:
        await asyncio.sleep(10)

    monkeypatch.setattr(fake_database, "ping", hang)
    monkeypatch.setattr(health, "POSTGRES_TIMEOUT", 0.05)

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["postgres"] == "error"
