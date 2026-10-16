"""Against a real Postgres at DATABASE_URL: CI starts one, locally compose.yaml does."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text

from candlestack.core import Base, Database, Settings
from candlestack.main import create_app

pytestmark = pytest.mark.integration


def test_health_with_postgres_up(redis_url: str, database_url: str) -> None:
    app = create_app(Settings(app_env="test", redis_url=redis_url, database_url=database_url))

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["postgres"] == "ok"


def test_health_with_postgres_unreachable(redis_url: str) -> None:
    app = create_app(
        Settings(
            app_env="test",
            redis_url=redis_url,
            database_url="postgresql+asyncpg://nobody:nothing@127.0.0.1:1/nothing",
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert response.json()["postgres"] == "error"


def _differences(connection: Connection) -> list[object]:
    return compare_metadata(MigrationContext.configure(connection), Base.metadata)


@pytest.mark.anyio
async def test_the_migrations_create_what_the_models_declare(database_url: str) -> None:
    db = Database(database_url)
    try:
        async with db.engine.connect() as connection:
            assert await connection.run_sync(_differences) == []
    finally:
        await db.dispose()


@pytest.mark.anyio
async def test_a_session_queries_the_database(database_url: str) -> None:
    db = Database(database_url)
    try:
        async with db.sessions() as session:
            assert await session.scalar(text("SELECT 1")) == 1
    finally:
        await db.dispose()
