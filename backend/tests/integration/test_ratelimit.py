"""RateLimiter against a real Redis at REDIS_URL."""

import logging
import os
import uuid
from collections.abc import AsyncIterator

import pytest
from redis.asyncio import Redis

import candlestack.core.ratelimit as ratelimit_module
from candlestack.core import RateLimiter, create_redis

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

MINUTE = 1_800_000_000  # a window start: a multiple of 60


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    client = create_redis(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    yield client
    await client.aclose()


@pytest.fixture
def key() -> str:
    return f"test:rl:{uuid.uuid4().hex}"


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """The limiter's time: set ``clock[0]``."""
    now = [MINUTE + 15.5]
    monkeypatch.setattr(ratelimit_module, "_time", lambda: now[0])
    return now


async def test_within_the_limit_then_until_the_window_resets(redis: Redis, key: str, clock):
    limiter = RateLimiter(redis)

    assert [await limiter.hit(key, 3) for _ in range(3)] == [0.0, 0.0, 0.0]
    assert await limiter.hit(key, 3) == 44.5
    clock[0] = MINUTE + 60  # the next window
    assert await limiter.hit(key, 3) == 0.0


async def test_cost_counts_and_keys_are_separate(redis: Redis, key: str, clock):
    limiter = RateLimiter(redis)

    assert await limiter.hit(key, 10, cost=8) == 0.0
    assert await limiter.hit(key, 10, cost=2) == 0.0
    assert await limiter.hit(key, 10, cost=2) == 44.5
    assert await limiter.hit(f"{key}:other", 10, cost=2) == 0.0


async def test_counter_expires_with_its_window(redis: Redis, key: str, clock):
    await RateLimiter(redis).hit(key, 5)

    assert 0 < await redis.ttl(f"{key}:{MINUTE // 60}") <= 61


async def test_zero_limit_disables_limiting(redis: Redis, key: str, clock):
    limiter = RateLimiter(redis)

    assert [await limiter.hit(key, 0) for _ in range(5)] == [0.0] * 5
    assert await redis.exists(f"{key}:{MINUTE // 60}") == 0


async def test_lets_requests_through_when_redis_fails(caplog: pytest.LogCaptureFixture):
    dead_redis = create_redis("redis://127.0.0.1:1/0")
    limiter = RateLimiter(dead_redis)

    with caplog.at_level(logging.WARNING):
        assert await limiter.hit("test:rl:dead", 1) == 0.0
        assert await limiter.hit("test:rl:dead", 1) == 0.0  # no second timeout: Redis skipped
    await dead_redis.aclose()

    assert caplog.text.count("rate limits are not counted") == 1
