"""Fixed-window rate limits counted in Redis: our budgets at the sources and per client."""

import ipaddress
import logging
import time
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# After Redis failed, hits pass without asking it for this long, so a dead Redis costs one
# timeout per few seconds instead of one per request.
DOWN_SECONDS = 5.0

# Patched by tests to control the window.
_time = time.time


class RateLimiter:
    """Counts cost per key in fixed windows (``window`` seconds, aligned to the epoch: with the
    default 60 the UTC minute). Counters live in Redis, so every process of an environment
    shares them."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._down_until = 0.0

    async def hit(self, key: str, limit: int, cost: int = 1, window: int = 60) -> float:
        """Adds cost to the fixed-window counter for key. Returns 0.0 when within the limit,
        otherwise the seconds until the window resets (the caller decides to wait or reject).
        limit <= 0 disables limiting.

        `key` is a Redis key prefix such as ``data:rl:alpaca``; the window number is appended.
        When Redis fails, hits are let through (fail open) for ``DOWN_SECONDS`` and a warning
        is logged: a lost counter must not take the API down.
        """
        if limit <= 0 or time.monotonic() < self._down_until:
            return 0.0
        now = _time()
        number = int(now // window)
        counter = f"{key}:{number}"
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incrby(counter, cost)
                pipe.expire(counter, window + 1)
                used, _ = await pipe.execute()
        except (RedisError, OSError) as exc:
            logger.warning(
                "Redis failed (%s): rate limits are not counted for %.0f s",
                type(exc).__name__,
                DOWN_SECONDS,
            )
            self._down_until = time.monotonic() + DOWN_SECONDS
            return 0.0
        if used <= limit:
            return 0.0
        return max((number + 1) * window - now, 0.001)

    async def used(self, key: str, window: int = 60) -> int | None:
        """The cost counted for ``key`` in the current window so far, or ``None`` when Redis
        cannot say (a log line can show it next to what a source reports)."""
        if time.monotonic() < self._down_until:
            return None
        try:
            value = await self._redis.get(f"{key}:{int(_time() // window)}")
        except (RedisError, OSError) as exc:
            logger.warning("Redis failed (%s): the %s count is not known", type(exc).__name__, key)
            return None
        return int(value or 0)


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]


def client_address(request: Request) -> str:
    """The client as the rate limits count it: Cloudflare's ``CF-Connecting-IP``, else the peer
    (local runs). An IPv6 client counts as its /64 network: a subscriber usually gets a whole
    /64, so single addresses would give one client any number of counters."""
    address = request.headers.get("cf-connecting-ip")
    if not address and request.client:
        address = request.client.host
    try:
        ip = ipaddress.ip_address(address or "")
    except ValueError:
        return address or "unknown"
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.IPv6Network((ip, 64), strict=False))
    return str(ip)
