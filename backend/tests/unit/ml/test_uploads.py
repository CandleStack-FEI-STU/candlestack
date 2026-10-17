"""The upload lock of a user, on a stand-in for Redis; with a real Redis:
tests/integration/ml."""

import logging
from typing import TYPE_CHECKING, cast

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from candlestack.ml.errors import UploadInProgress
from candlestack.ml.uploads import UPLOAD_LOCK_TTL, RedisUploadLocks

if TYPE_CHECKING:
    from redis.asyncio import Redis

pytestmark = pytest.mark.anyio


class FakeRedis:
    def __init__(self, *, release_fails: bool = False) -> None:
        self.values: dict[str, str] = {}
        self.expiries: dict[str, int] = {}
        self._release_fails = release_fails

    async def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
        assert nx
        if key in self.values:
            return False
        self.values[key] = value
        self.expiries[key] = ex
        return True

    async def eval(self, _script: str, _count: int, key: str, token: str) -> int:
        if self._release_fails:
            raise RedisConnectionError("Redis went away")
        if self.values.get(key) == token:
            del self.values[key]
            return 1
        return 0


def locks(redis: FakeRedis) -> RedisUploadLocks:
    return RedisUploadLocks(cast("Redis", redis))


async def test_the_lock_is_held_while_the_upload_runs() -> None:
    redis = FakeRedis()

    async with locks(redis).hold("usr_7f3k2m9qx4"):
        assert "ml:upload:usr_7f3k2m9qx4" in redis.values
        assert redis.expiries["ml:upload:usr_7f3k2m9qx4"] == UPLOAD_LOCK_TTL == 300

    assert redis.values == {}


async def test_a_second_upload_is_turned_away() -> None:
    redis = FakeRedis()

    async with locks(redis).hold("usr_7f3k2m9qx4"):
        with pytest.raises(UploadInProgress):
            async with locks(redis).hold("usr_7f3k2m9qx4"):
                pass
        assert "ml:upload:usr_7f3k2m9qx4" in redis.values  # the first upload's, still


async def test_the_lock_goes_when_the_upload_fails() -> None:
    redis = FakeRedis()

    with pytest.raises(RuntimeError):
        async with locks(redis).hold("usr_7f3k2m9qx4"):
            raise RuntimeError

    assert redis.values == {}


async def test_a_lock_that_cannot_be_released_expires(caplog: pytest.LogCaptureFixture) -> None:
    redis = FakeRedis(release_fails=True)

    with caplog.at_level(logging.WARNING):
        async with locks(redis).hold("usr_7f3k2m9qx4"):
            pass

    assert "The upload lock of user usr_7f3k2m9qx4 was not released (ConnectionError)" in (
        caplog.text
    )
