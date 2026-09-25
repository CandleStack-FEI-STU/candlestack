"""``GET /api/health``: liveness of the app and its Redis, read by deploy checks and ops."""

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import RedisError

from candlestack.core.config import SettingsDep
from candlestack.core.redis import RedisDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

REDIS_TIMEOUT = 2.0


class Health(BaseModel):
    status: Literal["ok", "error"]
    env: str
    version: str
    commit: str
    redis: Literal["ok", "error"]


@router.get(
    "/api/health",
    summary="Health of the app",
    responses={503: {"model": Health, "description": "Redis is unreachable"}},
)
async def health(settings: SettingsDep, redis: RedisDep, response: Response) -> Health:
    """200 when the app and its Redis work, 503 with the same body when Redis does not.

    The body is compact JSON: deploy checks look for `"version":"<version>"` and the commit.
    """
    redis_ok = await _ping(redis)
    if not redis_ok:
        response.status_code = 503
    return Health(
        status="ok" if redis_ok else "error",
        env=settings.app_env,
        version=settings.app_version,
        commit=settings.app_commit,
        redis="ok" if redis_ok else "error",
    )


async def _ping(redis: Redis) -> bool:
    try:
        async with asyncio.timeout(REDIS_TIMEOUT):
            await redis.ping()
    except (RedisError, OSError, TimeoutError) as exc:
        logger.warning("Redis ping failed: %s", type(exc).__name__)
        return False
    return True
