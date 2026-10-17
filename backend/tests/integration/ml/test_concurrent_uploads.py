"""Two uploads of one user at the same time, on the service with a real Postgres: the lock of
the user's models lets them keep files one after the other, so they cannot both pass the quota
or take the same name."""

import asyncio
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text

from candlestack.core import Database
from candlestack.ml import LocalModelStorage
from candlestack.ml.errors import StorageFull
from candlestack.ml.schemas import QUOTA_BYTES, ModelOut
from candlestack.ml.service import ModelsService
from candlestack.ml.store import ModelStore

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

USER = "usr_adaaaaaaaa"
CONTENT = (Path(__file__).parents[2] / "fixtures" / "keras" / "functional.keras").read_bytes()


@pytest.fixture
async def database(database_url: str) -> AsyncIterator[Database]:
    database = Database(database_url)
    now = datetime.now(UTC)
    async with database.sessions() as session:
        await session.execute(
            text("INSERT INTO users VALUES (:id, 'Ada', 'ada@example.com', :now, :now)"),
            {"id": USER, "now": now},
        )
        await session.commit()
    try:
        yield database
    finally:
        await database.dispose()


@pytest.fixture
async def storage(tmp_path: Path) -> LocalModelStorage:
    storage = LocalModelStorage(tmp_path / "models")
    await storage.prepare()
    return storage


async def fill(database: Database, size: int) -> None:
    async with database.sessions() as session:
        await session.execute(
            text(
                "INSERT INTO models (id, user_id, name, framework, size_bytes, sha256, "
                "parameters, keras_version, created_at) VALUES ('mdl_bigbigbigb', :user, "
                "'big.keras', 'keras', :size, :sha, 1, '3.15.1', now())"
            ),
            {"user": USER, "size": size, "sha": b"\0" * 32},
        )
        await session.commit()


async def upload_together(
    database: Database, storage: LocalModelStorage
) -> Sequence[ModelOut | BaseException]:
    """Two uploads whose files come in only once both passed the first look at the quota."""
    started = 0
    both = asyncio.Event()

    async def body() -> AsyncIterator[bytes]:
        nonlocal started
        started += 1
        if started == 2:
            both.set()
        await both.wait()
        yield CONTENT

    async def upload() -> ModelOut:
        async with database.sessions() as session:
            service = ModelsService(ModelStore(session), storage)
            return await service.upload(USER, "lstm.keras", len(CONTENT), body())

    return await asyncio.gather(upload(), upload(), return_exceptions=True)


async def test_only_one_of_two_uploads_fits(database: Database, storage: LocalModelStorage):
    # Room for one file, not two.
    await fill(database, QUOTA_BYTES - len(CONTENT) * 3 // 2)

    results = await upload_together(database, storage)

    kept = [result for result in results if isinstance(result, ModelOut)]
    refused = [result for result in results if isinstance(result, StorageFull)]
    assert len(kept) == 1
    assert len(refused) == 1
    assert refused[0].used_bytes == QUOTA_BYTES - len(CONTENT) * 3 // 2 + len(CONTENT)
    assert [path.name for path in (storage.path(USER, kept[0].id).parent).iterdir()] == [
        f"{kept[0].id}.keras"
    ]
    assert list((storage.path(USER, kept[0].id).parents[1] / ".incoming").iterdir()) == []


async def test_two_uploads_of_one_name_get_two_names(
    database: Database, storage: LocalModelStorage
) -> None:
    results = await upload_together(database, storage)

    assert sorted(result.name for result in results if isinstance(result, ModelOut)) == [
        "lstm (2).keras",
        "lstm.keras",
    ]
