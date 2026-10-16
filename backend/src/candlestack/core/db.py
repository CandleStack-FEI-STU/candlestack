"""Postgres: the store of what users create. Created in the app lifespan, reached through
``DbSessionDep``; the tables are declared on ``Base`` and changed only by Alembic migrations
(``backend/migrations``)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Stable constraint and index names, so a migration can name what an earlier one created.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# A small pool per process: the VM runs prod and stage against one small Postgres each, and
# requests hold a connection only while they query.
POOL_SIZE = 5
MAX_OVERFLOW = 5
POOL_TIMEOUT = 5.0
CONNECT_TIMEOUT = 2.0


class Base(DeclarativeBase):
    """The declarative base of every table of the app."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Database:
    """The engine (connection pool) and the session factory of one process."""

    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(
            url,
            pool_size=POOL_SIZE,
            max_overflow=MAX_OVERFLOW,
            pool_timeout=POOL_TIMEOUT,
            # A connection the server closed (restart, idle timeout) is replaced, not handed out.
            pool_pre_ping=True,
            connect_args={"timeout": CONNECT_TIMEOUT},
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def ping(self) -> None:
        """Raises when Postgres cannot answer a query."""
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self.engine.dispose()


def get_database(request: Request) -> Database:
    return request.app.state.db


DatabaseDep = Annotated[Database, Depends(get_database)]


async def get_db_session(db: DatabaseDep) -> AsyncIterator[AsyncSession]:
    """One session per request; what it changes is committed by the code that changes it."""
    async with db.sessions() as session:
        yield session


DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
