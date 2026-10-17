"""Alembic's environment: runs the migrations against ``DATABASE_URL``, or on the connection a
caller hands over in ``config.attributes["connection"]`` (the integration tests)."""

import asyncio

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

# Each module with tables declares them on Base.metadata when it is imported.
import candlestack.accounts
import candlestack.ml  # noqa: F401
from candlestack.core import Base, get_settings, setup_logging


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_on_database_url() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url.get_secret_value(), poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


if (given := context.config.attributes.get("connection")) is not None:
    run_migrations(given)
else:
    setup_logging(get_settings().log_level)
    asyncio.run(run_on_database_url())
