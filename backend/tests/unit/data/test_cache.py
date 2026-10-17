"""The cache when Redis fails part-way: every call works on without it, logs one warning and
leaves Redis alone for the back-off window."""

import logging
import time
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

import candlestack.data.cache as cache_module
from candlestack.data import SourceUnavailable
from candlestack.data.cache import DOWN_SECONDS, Cache

if TYPE_CHECKING:
    from redis.asyncio import Redis

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
        return Cache(cast("Redis", self))


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


async def test_values_are_misses(error: Exception, caplog: pytest.LogCaptureFixture) -> None:
    redis = FailingRedis(error)
    cache = redis.cache()

    assert await cache.get_many(["first:crypto:BTCUSDT", "first:stock:AAPL"]) == [None, None]
    assert await cache.get_many(["first:crypto:BTCUSDT"]) == [None]  # Redis is left alone

    assert redis.calls == ["mget"]
    assert warned(caplog, error) == 1


async def test_no_values_ask_nothing(error: Exception) -> None:
    redis = FailingRedis(error)

    assert await redis.cache().get_many([]) == []
    assert redis.calls == []


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
    # Redis answers the lookup, the lock and the second lookup, then goes away before the value
    # is stored.
    redis = FailingRedis(error, up=3)

    assert await redis.cache().get_or_fetch("calendar", fetch) == b"fetched"

    # lookup, lock, lookup again, the value; no release
    assert redis.calls == ["mget", "set", "mget", "set"]
    assert warned(caplog, error) == 1


async def test_a_failed_fetch_keeps_its_error_when_redis_fails_too(
    error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    redis = FailingRedis(error, up=3)

    async def timeout() -> tuple[bytes, int]:
        raise SourceUnavailable("binance", "Binance did not answer in time. Try again in a minute.")

    with pytest.raises(SourceUnavailable, match="Binance did not answer in time"):
        await redis.cache().get_or_fetch("calendar", timeout)

    # lookup, lock, lookup again, the error; no release
    assert redis.calls == ["mget", "set", "mget", "set"]
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


class ScriptedRedis:
    """Answers each command from a script, in order, and records the commands."""

    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.calls: list[str] = []

    def __getattr__(self, command: str) -> Any:
        async def send(*args: Any, **kwargs: Any) -> Any:
            self.calls.append(command)
            return self.replies.pop(0)

        return send


async def test_a_value_stored_between_the_lookup_and_the_lock_is_not_fetched_again() -> None:
    # The holder stores the value and releases the lock after our lookup and before our lock:
    # the lookup finds nothing, the lock is free, and only a second lookup finds the value.
    redis = ScriptedRedis([None, None], True, [b"stored", None], 1)

    async def never() -> tuple[bytes, int]:
        raise AssertionError("fetched twice")

    assert await Cache(cast("Redis", redis)).get_or_fetch("calendar", never) == b"stored"

    assert redis.calls == ["mget", "set", "mget", "eval"]  # the lock is released, not kept


async def test_an_error_stored_between_the_lookup_and_the_lock_is_raised() -> None:
    failure = cache_module._encode_failure(SourceUnavailable("binance", "Binance is down."))[0]
    redis = ScriptedRedis([None, None], True, [None, failure], 1)

    async def never() -> tuple[bytes, int]:
        raise AssertionError("fetched twice")

    with pytest.raises(SourceUnavailable, match="Binance is down"):
        await Cache(cast("Redis", redis)).get_or_fetch("calendar", never)

    assert redis.calls == ["mget", "set", "mget", "eval"]


def test_locks_and_kept_errors_are_versioned_with_their_values() -> None:
    # During a deploy, a process on catalog v1 and one on v2 must not share a lock or an error
    # while they wait for different values.
    assert cache_module.key("catalog:crypto") == "data:v2:catalog:crypto"
    assert cache_module.lock_key("catalog:crypto") == "data:lock:v2:catalog:crypto"
    assert cache_module.fail_key("catalog:crypto") == "data:fail:v2:catalog:crypto"
    assert cache_module.lock_key("calendar") == "data:lock:v1:calendar"


@pytest.mark.parametrize(
    ("name", "stored"),
    [
        # The stocks' values from IEX are never read again; the crypto ones stay.
        ("candles:stock:AAPL:1m:2024-06", "data:v3:candles:stock:AAPL:1m:2024-06"),
        ("candles:crypto:BTCUSDT:1h:2024-06", "data:v2:candles:crypto:BTCUSDT:1h:2024-06"),
        ("first:stock:AAPL", "data:v2:first:stock:AAPL"),
        ("first:crypto:BTCUSDT", "data:v1:first:crypto:BTCUSDT"),
        ("stats:stock", "data:v2:stats:stock"),
        ("stats:crypto", "data:v1:stats:crypto"),
        ("spark:stock", "data:v2:spark:stock"),
        ("spark:crypto", "data:v1:spark:crypto"),
        ("catalog:stock", "data:v2:catalog:stock"),
        ("health:alpaca", "data:v1:health:alpaca"),
    ],
)
def test_a_market_can_have_its_own_version_of_a_family(name: str, stored: str) -> None:
    assert cache_module.key(name) == stored
    assert cache_module.lock_key(name) == stored.replace("data:", "data:lock:", 1)


async def test_a_lock_is_kept_without_redis(error: Exception, caplog: pytest.LogCaptureFixture):
    # Without Redis nobody else can take it: renewing it succeeds, now and while Redis is skipped.
    cache = FailingRedis(error).cache()

    assert await cache.extend("stats:stock", "token", 1000) is True
    assert await cache.extend("stats:stock", "token", 1000) is True
    assert warned(caplog, error) == 1


async def test_a_header_is_not_read_without_redis(
    error: Exception, caplog: pytest.LogCaptureFixture
):
    redis = FailingRedis(error)
    cache = redis.cache()

    assert await cache.head("stats:stock", 8) is None
    assert await cache.head("stats:stock", 8) is None
    assert redis.calls == ["getrange"]
    assert warned(caplog, error) == 1
