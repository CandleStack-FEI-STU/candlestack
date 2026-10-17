"""Fixtures of the models integration tests: the app on a real Postgres (emptied before each
test) with its model storage in a temporary directory, and signed-in users made straight in
the database.

Test modules cannot import this file, so the helpers they need hang on the ``Account`` the
``ada`` and ``bob`` fixtures return, and on ``Storage``.
"""

import asyncio
import hashlib
import secrets
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from candlestack.core import Settings
from candlestack.main import create_app

ORIGIN = {"Origin": "http://testserver"}


async def _run_sql(url: str, statement: str, params: dict[str, Any]) -> list[Any]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            result = await connection.execute(text(statement), params)
            return list(result.all()) if result.returns_rows else []
    finally:
        await engine.dispose()


@pytest.fixture
def sql(database_url: str) -> Callable[..., list[Any]]:
    """Runs one statement in the test database: ``sql("SELECT id FROM models")``, the rows."""
    return lambda statement, **params: asyncio.run(_run_sql(database_url, statement, params))


@pytest.fixture(autouse=True)
def empty_tables(sql: Callable[..., list[Any]]) -> None:
    sql("TRUNCATE users, identities, sessions, user_preferences, models")


@pytest.fixture
def settings(database_url: str, redis_url: str, tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        database_url=database_url,
        redis_url=redis_url,
        model_storage_dir=tmp_path / "models",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


class Storage:
    """The model storage's directory."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def file(self, user_id: str, model_id: str) -> Path:
        return self.root / user_id / f"{model_id}.keras"

    def incoming(self) -> list[Path]:
        """What uploads left in the incoming directory."""
        return list((self.root / ".incoming").iterdir())

    def files(self) -> list[Path]:
        """Every model file, of every user."""
        return sorted(path for path in self.root.glob("usr_*/*") if path.is_file())


@pytest.fixture
def storage(settings: Settings) -> Storage:
    return Storage(settings.model_storage_dir)


class Account:
    """A signed-in user: a row in ``users`` and a session whose cookie each request carries."""

    def __init__(self, client: TestClient, sql: Callable[..., list[Any]], user_id: str) -> None:
        self.id = user_id
        self._client = client
        self._token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        sql(
            "INSERT INTO users VALUES (:id, :name, :email, :now, :now)",
            id=user_id,
            name=user_id,
            email=f"{user_id}@example.com",
            now=now,
        )
        sql(
            "INSERT INTO sessions VALUES (:hash, :id, :now, :now, :expires)",
            hash=hashlib.sha256(self._token.encode()).digest(),
            id=user_id,
            now=now,
            expires=now + timedelta(days=30),
        )

    def request(self, method: str, url: str, **kwargs: Any) -> httpx2.Response:
        headers = {**ORIGIN, "Cookie": f"session={self._token}", **kwargs.pop("headers", {})}
        self._client.cookies.clear()
        return self._client.request(method, url, headers=headers, **kwargs)

    def upload(self, content: bytes | Any, name: str = "functional.keras") -> httpx2.Response:
        return self.request("POST", "/api/v1/models", params={"name": name}, content=content)

    def models(self) -> httpx2.Response:
        return self.request("GET", "/api/v1/models")

    def update(self, model_id: str, **body: Any) -> httpx2.Response:
        return self.request("PATCH", f"/api/v1/models/{model_id}", json=body)

    def delete(self, model_id: str) -> httpx2.Response:
        return self.request("DELETE", f"/api/v1/models/{model_id}")


@pytest.fixture
def ada(client: TestClient, sql: Callable[..., list[Any]]) -> Account:
    return Account(client, sql, "usr_adaaaaaaaa")


@pytest.fixture
def bob(client: TestClient, sql: Callable[..., list[Any]]) -> Account:
    return Account(client, sql, "usr_bobbbbbbbb")
