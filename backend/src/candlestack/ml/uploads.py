"""One upload in progress per user: a lock in Redis that ends with the upload, or after
``UPLOAD_LOCK_TTL`` when the process died during it. A user cannot fill the disk with uploads
side by side, each within the quota until it is kept."""

import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol

import anyio
from redis.asyncio import Redis
from redis.exceptions import RedisError

from candlestack.ml.errors import UploadInProgress

logger = logging.getLogger(__name__)

# Longer than an upload may take: receiving it (2 minutes), waiting for the check and the check.
UPLOAD_LOCK_TTL = 300
# Deletes the lock only while it is still this upload's: one that expired may be another's.
_RELEASE = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


class UploadLocks(Protocol):
    def hold(self, user_id: str) -> AbstractAsyncContextManager[None]:
        """Holds the user's upload lock while the block runs.

        Raises:
            UploadInProgress: Another upload of the user holds it.
        """
        ...


class RedisUploadLocks:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @asynccontextmanager
    async def hold(self, user_id: str) -> AsyncIterator[None]:
        key = f"ml:upload:{user_id}"
        token = secrets.token_hex(16)
        if not await self._redis.set(key, token, nx=True, ex=UPLOAD_LOCK_TTL):
            raise UploadInProgress
        try:
            yield
        finally:
            with anyio.CancelScope(shield=True):
                try:
                    await self._redis.eval(_RELEASE, 1, key, token)
                except RedisError as error:
                    # The lock expires by itself; until then the user's next upload waits.
                    logger.warning(
                        "The upload lock of user %s was not released (%s)",
                        user_id,
                        type(error).__name__,
                    )
