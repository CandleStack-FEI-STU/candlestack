"""Keeping a checked upload when Postgres refuses the row for another reason than a deleted
account: the error goes on as it is. The flows with a real Postgres: tests/integration/ml."""

from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from sqlalchemy.exc import IntegrityError

from candlestack.ml.inspect import ModelFacts
from candlestack.ml.service import ModelsService

if TYPE_CHECKING:
    from candlestack.ml.storage import ModelStorage
    from candlestack.ml.store import ModelStore
    from candlestack.ml.uploads import UploadLocks

pytestmark = pytest.mark.anyio


class UniqueViolation(Exception):
    sqlstate = "23505"


class FakeStore:
    async def lock_user(self, user_id: str) -> None:
        pass

    async def usage(self, user_id: str) -> tuple[int, int]:
        return 0, 0

    async def names_starting(self, user_id: str, prefix: str) -> list[str]:
        return []

    def add(self, model: object) -> None:
        pass

    async def flush(self) -> None:
        raise IntegrityError("INSERT INTO models", None, UniqueViolation())


async def test_another_integrity_error_goes_on(tmp_path: Path) -> None:
    service = ModelsService(
        cast("ModelStore", FakeStore()), cast("ModelStorage", None), cast("UploadLocks", None)
    )

    with pytest.raises(IntegrityError):
        await service._keep(
            "usr_7f3k2m9qx4",
            tmp_path / "upload.part",
            name="lstm.keras",
            size=10,
            sha256=b"\0" * 32,
            facts=ModelFacts("3.15.1", 1, None, None),
        )
