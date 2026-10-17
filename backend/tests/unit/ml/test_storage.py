"""The model files in a directory."""

import logging
import os
import time
from pathlib import Path

import pytest

from candlestack.ml.storage import LocalModelStorage

pytestmark = pytest.mark.anyio

USER = "usr_7f3k2m9qx4"


@pytest.fixture
async def storage(tmp_path: Path) -> LocalModelStorage:
    storage = LocalModelStorage(tmp_path / "models")
    await storage.prepare()
    return storage


async def incoming(storage: LocalModelStorage, content: bytes = b"model") -> Path:
    path = storage.incoming_path()
    path.write_bytes(content)
    return path


async def test_prepare_creates_the_directories(tmp_path: Path) -> None:
    await LocalModelStorage(tmp_path / "var" / "models").prepare()

    assert (tmp_path / "var" / "models" / ".incoming").is_dir()


async def test_incoming_files_are_new_part_files(storage: LocalModelStorage, tmp_path: Path):
    first, second = storage.incoming_path(), storage.incoming_path()

    assert first != second
    assert first.parent == second.parent == tmp_path / "models" / ".incoming"
    assert first.suffix == ".part"


async def test_save_moves_the_file_to_the_users_directory(
    storage: LocalModelStorage, tmp_path: Path
) -> None:
    path = await incoming(storage)

    await storage.save(path, USER, "mdl_aaaaaaaaaa")

    assert not path.exists()
    assert (tmp_path / "models" / USER / "mdl_aaaaaaaaaa.keras").read_bytes() == b"model"
    assert (
        storage.path(USER, "mdl_aaaaaaaaaa") == tmp_path / "models" / USER / "mdl_aaaaaaaaaa.keras"
    )


async def test_delete_removes_one_file(storage: LocalModelStorage) -> None:
    await storage.save(await incoming(storage), USER, "mdl_aaaaaaaaaa")
    await storage.save(await incoming(storage), USER, "mdl_bbbbbbbbbb")

    await storage.delete(USER, "mdl_aaaaaaaaaa")
    await storage.delete(USER, "mdl_aaaaaaaaaa")  # gone already is fine

    assert not storage.path(USER, "mdl_aaaaaaaaaa").exists()
    assert storage.path(USER, "mdl_bbbbbbbbbb").exists()


async def test_delete_user_removes_the_users_directory(
    storage: LocalModelStorage, tmp_path: Path
) -> None:
    await storage.save(await incoming(storage), USER, "mdl_aaaaaaaaaa")
    await storage.save(await incoming(storage), "usr_other00000", "mdl_bbbbbbbbbb")

    await storage.delete_user(USER)
    await storage.delete_user(USER)  # a user without files is fine

    assert not (tmp_path / "models" / USER).exists()
    assert storage.path("usr_other00000", "mdl_bbbbbbbbbb").exists()


async def test_discard_removes_an_incoming_file(storage: LocalModelStorage) -> None:
    path = await incoming(storage)

    await storage.discard(path)
    await storage.discard(path)

    assert not path.exists()


async def test_prepare_removes_what_crashed_uploads_left(
    storage: LocalModelStorage, caplog: pytest.LogCaptureFixture
) -> None:
    stale, fresh = await incoming(storage), await incoming(storage)
    two_hours_ago = time.time() - 7200
    os.utime(stale, (two_hours_ago, two_hours_ago))

    with caplog.at_level(logging.INFO):
        await storage.prepare()

    assert not stale.exists()
    assert fresh.exists()  # an upload in progress
    assert "Removed 1 incoming model files that crashed uploads left" in caplog.text
