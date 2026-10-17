"""Fixtures of the integration tests: a real Redis at REDIS_URL and a real Postgres at
DATABASE_URL (CI starts both, locally the ones of compose.yaml).

Without REDIS_URL the tests use DB 15 of the local Redis, not the dev backend's DB 0: the data
tests flush their database before each test. Without DATABASE_URL they use the database
``candlestack_test`` of the local Postgres, which they create when it is missing; the first test
that needs it migrates it down to nothing and up again (migrations/), and the tests empty its
tables before each test. Never point them at a database whose data you need.
"""

import asyncio
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, make_url, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

BACKEND = Path(__file__).parents[2]
LOCAL_DATABASE_URL = "postgresql+asyncpg://candlestack:candlestack@127.0.0.1:5432/candlestack_test"


@pytest.fixture
def redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/15")


def alembic_config(connection: Connection) -> Config:
    """The project's Alembic configuration, running on `connection`."""
    config = Config(toml_file=BACKEND / "pyproject.toml")
    config.attributes["connection"] = connection
    return config


def _migrate_from_scratch(connection: Connection) -> None:
    config = alembic_config(connection)
    command.downgrade(config, "base")
    command.upgrade(config, "head")


async def _prepare(url: str) -> None:
    """Creates the database when missing, then migrates it down to nothing and up again."""
    name = make_url(url).database
    server = create_async_engine(
        make_url(url).set(database="postgres"), poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    try:
        async with server.connect() as connection:
            exists = await connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
            )
            if not exists:
                await connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await server.dispose()
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_migrate_from_scratch)
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("DATABASE_URL") or LOCAL_DATABASE_URL
    asyncio.run(_prepare(url))
    return url
