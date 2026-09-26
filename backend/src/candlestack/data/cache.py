"""The Redis cache of the data module: values fetched once (single-flight), candle chunks as
Arrow IPC with zstd, and the errors of failed fetches for a few seconds.

Redis is disposable here. When it fails, values are fetched from the source and not cached,
a warning is logged and the cache is skipped for a few seconds; a Redis failure never fails a
request by itself.
"""

import asyncio
import io
import logging
import math
import secrets
import struct
import time
from collections.abc import Awaitable, Callable

import orjson
import polars as pl
from redis.asyncio import Redis
from redis.exceptions import RedisError

from candlestack.data.errors import DataIntegrityError, SourceUnavailable

logger = logging.getLogger(__name__)

KEY_PREFIX = "data:v1:"
LOCK_PREFIX = "data:lock:"
FAIL_PREFIX = "data:fail:"
LOCK_TTL_MS = 30_000
# How long the error of a failed fetch is kept: the callers waiting for the value and new ones
# get it at once, instead of calling the source again one after another.
FAIL_SECONDS = 10
POLL_SECONDS = 0.1
# How long the cache is skipped after Redis failed, so that a dead Redis costs one timeout
# per few seconds instead of one per call.
DOWN_SECONDS = 5.0

_REDIS_ERRORS = (RedisError, OSError)
# Deletes the lock only if it is still ours (it may have expired and been taken by another).
_RELEASE = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0"
)
_HEADER = struct.Struct(">q")

# Patched by tests to avoid real waiting.
_sleep = asyncio.sleep

Fetch = Callable[[], Awaitable[tuple[bytes, int]]]
"""Produces a value to cache and the seconds to keep it."""


class Cache:
    """Values under ``data:v1:<name>``; ``name`` is e.g. ``calendar`` or
    ``candles:crypto:BTCUSDT:1h:2024-01``."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._down_until = 0.0

    async def get(self, name: str) -> bytes | None:
        """The cached value, or ``None`` on a miss or when Redis fails."""
        if self._is_down():
            return None
        try:
            # redis-py types values as bytes | str; this client never decodes (create_redis).
            return await self._redis.get(KEY_PREFIX + name)  # ty: ignore[invalid-return-type]
        except _REDIS_ERRORS as exc:
            self._failed(exc)
            return None

    async def set(self, name: str, value: bytes, ttl: int) -> None:
        """Stores a value for ``ttl`` seconds; a Redis failure only logs."""
        await self._store(KEY_PREFIX + name, value, ttl)

    async def delete(self, name: str) -> None:
        """Removes a value; a Redis failure only logs."""
        if self._is_down():
            return
        try:
            await self._redis.delete(KEY_PREFIX + name)
        except _REDIS_ERRORS as exc:
            self._failed(exc)

    async def get_or_fetch(self, name: str, fetch: Fetch) -> bytes:
        """The cached value, or the one ``fetch`` produces, which is then cached.

        Single-flight: one caller takes the lock ``data:lock:<name>`` (``SET NX``, 30 s) and
        fetches; concurrent callers poll until the value appears, or take the lock themselves
        when it expires. When ``fetch`` fails with ``SourceUnavailable`` or
        ``DataIntegrityError``, the error is kept as ``data:fail:<name>`` for ``FAIL_SECONDS``
        (at most its ``retry_after``): the waiting callers and new ones raise it without calling
        the source. Other errors propagate and nothing is kept.
        """
        lock, token = LOCK_PREFIX + name, secrets.token_hex(8)
        while True:
            if self._is_down():
                return (await fetch())[0]
            try:
                value, failure = await self._redis.mget(KEY_PREFIX + name, FAIL_PREFIX + name)
                if value is not None:
                    # redis-py types values as bytes | str; this client never decodes.
                    return value  # ty: ignore[invalid-return-type]
                if failure is not None:
                    raise _decode_failure(failure)
                if await self._redis.set(lock, token, nx=True, px=LOCK_TTL_MS):
                    break
            except _REDIS_ERRORS as exc:
                self._failed(exc)
                return (await fetch())[0]
            await _sleep(POLL_SECONDS)
        try:
            try:
                value, ttl = await fetch()
            except (SourceUnavailable, DataIntegrityError) as exc:
                await self._store(FAIL_PREFIX + name, *_encode_failure(exc))
                raise
            await self.set(name, value, ttl)
            return value
        finally:
            await self._release(lock, token)

    async def lock(self, name: str) -> str | None:
        """Takes the single-flight lock of ``name`` without waiting: a token to give back with
        ``unlock``, or ``None`` when another holds the lock. Without Redis there is nobody to
        coordinate with, so the lock is granted."""
        token = secrets.token_hex(8)
        if self._is_down():
            return token
        try:
            taken = await self._redis.set(LOCK_PREFIX + name, token, nx=True, px=LOCK_TTL_MS)
        except _REDIS_ERRORS as exc:
            self._failed(exc)
            return token
        return token if taken else None

    async def unlock(self, name: str, token: str) -> None:
        await self._release(LOCK_PREFIX + name, token)

    async def _store(self, key: str, value: bytes, ttl: int) -> None:
        if self._is_down():
            return
        try:
            await self._redis.set(key, value, ex=ttl)
        except _REDIS_ERRORS as exc:
            self._failed(exc)

    async def _release(self, lock: str, token: str) -> None:
        if self._is_down():
            return
        try:
            await self._redis.eval(_RELEASE, 1, lock, token)
        except _REDIS_ERRORS as exc:
            self._failed(exc)

    def _is_down(self) -> bool:
        return time.monotonic() < self._down_until

    def _failed(self, exc: BaseException) -> None:
        logger.warning(
            "Redis failed (%s): working without the cache for %.0f s",
            type(exc).__name__,
            DOWN_SECONDS,
        )
        self._down_until = time.monotonic() + DOWN_SECONDS


def _encode_failure(error: SourceUnavailable | DataIntegrityError) -> tuple[bytes, int]:
    """A failed fetch's error as kept in Redis, and how long to keep it."""
    ttl = FAIL_SECONDS
    retry_at = None
    if isinstance(error, SourceUnavailable) and error.retry_after is not None:
        ttl = max(1, min(ttl, error.retry_after))
        retry_at = time.time() + error.retry_after
    kind = "unavailable" if isinstance(error, SourceUnavailable) else "invalid"
    value = {"kind": kind, "source": error.source, "detail": error.detail, "retry_at": retry_at}
    return orjson.dumps(value), ttl


def _decode_failure(blob: bytes | str) -> SourceUnavailable | DataIntegrityError:
    value = orjson.loads(blob)
    if value["kind"] == "invalid":
        return DataIntegrityError(value["detail"], source=value["source"])
    retry_at = value["retry_at"]
    retry_after = None if retry_at is None else max(1, math.ceil(retry_at - time.time()))
    return SourceUnavailable(value["source"], value["detail"], retry_after=retry_after)


def encode_chunk(frame: pl.DataFrame, fetched_at: int) -> bytes:
    """A candle chunk as cached: the fetch time (big-endian int64 epoch seconds), then the frame
    as Arrow IPC with zstd."""
    buffer = io.BytesIO()
    buffer.write(_HEADER.pack(fetched_at))
    frame.write_ipc(buffer, compression="zstd")
    return buffer.getvalue()


def decode_chunk(blob: bytes) -> tuple[pl.DataFrame, int]:
    """The frame and fetch time of an ``encode_chunk`` blob."""
    (fetched_at,) = _HEADER.unpack_from(blob)
    return pl.read_ipc(io.BytesIO(blob[_HEADER.size :])), fetched_at
