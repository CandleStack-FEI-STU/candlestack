"""Redis: the cache of the app. Created in the app lifespan, reached through ``RedisDep``."""

from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialWithJitterBackoff


def create_redis(url: str) -> Redis:
    """A client that fails fast: a cache miss is better than a request stuck on a dead cache.

    Responses stay bytes (``decode_responses=False``), as cached blobs are binary.
    """
    return Redis.from_url(
        url,
        socket_connect_timeout=1,
        socket_timeout=2,
        retry=Retry(ExponentialWithJitterBackoff(base=0.05, cap=0.5), retries=2),
        health_check_interval=30,
    )


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


RedisDep = Annotated[Redis, Depends(get_redis)]
