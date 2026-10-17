"""``GET /api/health``: liveness of the app, its Redis and its Postgres, read by deploy checks
and ops."""

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import RedisError

from candlestack.core.config import SettingsDep
from candlestack.core.db import DATABASE_ERRORS, Database, DatabaseDep
from candlestack.core.redis import RedisDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

REDIS_TIMEOUT = 2.0
POSTGRES_TIMEOUT = 2.0

Check = Literal["ok", "error"]


class Health(BaseModel):
    status: Check
    env: str
    version: str
    commit: str
    redis: Check
    postgres: Check


@router.get(
    "/api/health",
    summary="Health of the app",
    responses={503: {"model": Health, "description": "Redis or Postgres is unreachable"}},
)
async def health(
    settings: SettingsDep, redis: RedisDep, db: DatabaseDep, response: Response
) -> Health:
    """200 when the app, its Redis and its Postgres work, 503 with the same body when one of
    them does not.

    The body is compact JSON: deploy checks look for `"version":"<version>"` and the commit.
    """
    redis_ok, postgres_ok = await asyncio.gather(_ping_redis(redis), _ping_postgres(db))
    ok = redis_ok and postgres_ok
    if not ok:
        response.status_code = 503
    return Health(
        status=_check(ok),
        env=settings.app_env,
        version=settings.app_version,
        commit=settings.app_commit,
        redis=_check(redis_ok),
        postgres=_check(postgres_ok),
    )


def _check(ok: bool) -> Check:  # noqa: FBT001 (the result of a check)
    return "ok" if ok else "error"


async def _ping_redis(redis: Redis) -> bool:
    try:
        async with asyncio.timeout(REDIS_TIMEOUT):
            await redis.ping()
    except (RedisError, OSError, TimeoutError) as exc:
        logger.warning("Redis ping failed: %s", type(exc).__name__)
        return False
    return True


async def _ping_postgres(db: Database) -> bool:
    try:
        async with asyncio.timeout(POSTGRES_TIMEOUT):
            await db.ping()
    except DATABASE_ERRORS as exc:
        logger.warning("Postgres ping failed: %s", type(exc).__name__)
        return False
    return True
