"""The cache when Redis fails part-way: every call works on without it, logs one warning and
leaves Redis alone for the back-off window."""

import logging
import time
from types import SimpleNamespace
from typing import Any, cast

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

import candlestack.data.cache as cache_module
from candlestack.data import SourceUnavailable
from candlestack.data.cache import DOWN_SECONDS, Cache

pytestmark = pytest.mark.anyio

# What an empty Redis answers to the commands the cache sends.
EMPTY_REPLIES = {"get": None, "mget": [None, None], "set": True, "delete": 0, "eval": 1}


class FailingRedis:
    """Answers its first ``up`` commands like an empty Redis, then fails every command with
    ``error``, like a Redis that goes away mid-way. ``calls`` names the commands it got."""

    def __init__(self, error: Exception, up: int = 0) -> None:
        self.error = error
        self.up = up
        self.calls: list[str] = []

    def __getattr__(self, command: str) -> Any:
        async def send(*args: Any, **kwargs: Any) -> Any:
            self.calls.append(command)
            if len(self.calls) > self.up:
                raise self.error
            return EMPTY_REPLIES[command]

        return send

    def cache(self) -> Cache:
        return Cache(cast(Redis, self))


@pytest.fixture(
    params=[
        RedisConnectionError("Connection closed by server."),
        RedisTimeoutError("Timeout reading from socket"),
    ],
    ids=["connection-error", "timeout"],
)
def error(request: pytest.FixtureRequest) -> Exception:
    return request.param


@pytest.fixture(autouse=True)
def capture_warnings(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)


def warned(caplog: pytest.LogCaptureFixture, error: Exception) -> int:
    """How often the cache warned that Redis failed with ``error``."""
    message = f"Redis failed ({type(error).__name__}): working without the cache for 5 s"
    return sum(
        record.levelno == logging.WARNING and record.getMessage() == message
        for record in caplog.records
    )


async def fetch() -> tuple[bytes, int]:
    return b"fetched", 60


async def test_a_value_is_a_miss(error: Exception, caplog: pytest.LogCaptureFixture) -> None:
    redis = FailingRedis(error)

    assert await redis.cache().get("calendar") is None

    assert redis.calls == ["get"]
    assert warned(caplog, error) == 1


@pytest.mark.parametrize(
    ("write", "command"),
    [
        (lambda cache: cache.set("calendar", b"[]", 60), "set"),
        (lambda cache: cache.delete("calendar"), "delete"),
        (lambda cache: cache.unlock("catalog:crypto", "5f2b9c0e1d3a4b67"), "eval"),
    ],
    ids=["set", "delete", "unlock"],
)
async def test_a_write_only_logs(
    write: Any, command: str, error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    redis = FailingRedis(error)

    await write(redis.cache())

    assert redis.calls == [command]
    assert warned(caplog, error) == 1


async def test_the_lock_is_granted(error: Exception, caplog: pytest.LogCaptureFixture) -> None:
    # Without Redis there is nobody to coordinate with: the caller fetches.
    redis = FailingRedis(error)
    cache = redis.cache()

    token = await cache.lock("catalog:crypto")
    await cache.unlock("catalog:crypto", token or "")

    assert token
    assert redis.calls == ["set"]  # the unlock did not ask the Redis that just failed
    assert warned(caplog, error) == 1


async def test_a_value_is_fetched_and_not_cached(
    error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    redis = FailingRedis(error)

    assert await redis.cache().get_or_fetch("calendar", fetch) == b"fetched"

    assert redis.calls == ["mget"]
    assert warned(caplog, error) == 1


async def test_redis_fails_after_the_lock_was_taken(
    error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    # Redis answers the lookup and the lock, then goes away before the value is stored.
    redis = FailingRedis(error, up=2)

    assert await redis.cache().get_or_fetch("calendar", fetch) == b"fetched"

    assert redis.calls == ["mget", "set", "set"]  # lookup, lock, the value; no release
    assert warned(caplog, error) == 1


async def test_a_failed_fetch_keeps_its_error_when_redis_fails_too(
    error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    redis = FailingRedis(error, up=2)

    async def timeout() -> tuple[bytes, int]:
        raise SourceUnavailable("binance", "Binance did not answer in time. Try again in a minute.")

    with pytest.raises(SourceUnavailable, match="Binance did not answer in time"):
        await redis.cache().get_or_fetch("calendar", timeout)

    assert redis.calls == ["mget", "set", "set"]  # lookup, lock, the error; no release
    assert warned(caplog, error) == 1


async def test_redis_is_left_alone_for_the_back_off_window(
    error: Exception, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [1000.0]
    monkeypatch.setattr(
        cache_module, "time", SimpleNamespace(monotonic=lambda: now[0], time=time.time)
    )
    redis = FailingRedis(error)
    cache = redis.cache()

    assert await cache.get("calendar") is None
    now[0] += DOWN_SECONDS - 0.1
    assert await cache.get("calendar") is None
    await cache.set("calendar", b"[]", 60)
    await cache.delete("calendar")
    token = await cache.lock("catalog:crypto")
    await cache.unlock("catalog:crypto", token or "")
    assert await cache.get_or_fetch("calendar", fetch) == b"fetched"
    assert token
    assert redis.calls == ["get"]
    assert warned(caplog, error) == 1

    now[0] += 0.1  # the window is over: Redis is asked again
    assert await cache.get("calendar") is None

    assert redis.calls == ["get", "get"]
    assert warned(caplog, error) == 2
