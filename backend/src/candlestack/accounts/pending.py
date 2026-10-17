"""What a sign-in keeps between its requests, in Redis for 10 minutes: the state of a sign-in
on its way to the provider and back (``auth:state:<sha256 of the state>``), and the account the
beta list just turned away (``auth:denied:<sha256 of its id>``), which the sign-in page asks
for. The keys hold hashes only: whoever knows a state or an id can use it, and Redis keys show
up in traces."""

import hashlib
import logging
import secrets

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from redis.exceptions import RedisError

from candlestack.accounts.errors import SignInFailed
from candlestack.accounts.schemas import DeniedSignInOut, Provider

logger = logging.getLogger(__name__)

# Seconds a sign-in may take at the provider, and the sign-in page may show a denial.
TTL = 600


def _key(kind: str, value: str) -> str:
    return f"auth:{kind}:{hashlib.sha256(value.encode()).hexdigest()}"


class PendingSignIn(BaseModel):
    provider: Provider
    verifier: str = Field(repr=False)  # Sentry keeps the reprs of a failed frame's variables
    next: str


class PendingStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def put_sign_in(self, state: str, pending: PendingSignIn) -> None:
        """Raises SignInFailed when Redis fails."""
        try:
            await self._redis.set(_key("state", state), pending.model_dump_json(), ex=TTL)
        except (RedisError, OSError) as error:
            raise SignInFailed(f"Redis failed ({type(error).__name__})") from error

    async def take_sign_in(self, state: str) -> PendingSignIn | None:
        """The sign-in of `state`, once: a second read finds nothing.

        Raises:
            SignInFailed: Redis failed.
        """
        try:
            value = await self._redis.getdel(_key("state", state))
        except (RedisError, OSError) as error:
            raise SignInFailed(f"Redis failed ({type(error).__name__})") from error
        return None if value is None else PendingSignIn.model_validate_json(value)

    async def put_denial(self, email: str, provider: Provider) -> str:
        """Keeps the account the beta list turned away; returns its random ID.

        Raises:
            SignInFailed: Redis failed.
        """
        denial_id = secrets.token_urlsafe(16)
        body = DeniedSignInOut(email=email, provider=provider).model_dump_json()
        try:
            await self._redis.set(_key("denied", denial_id), body, ex=TTL)
        except (RedisError, OSError) as error:
            raise SignInFailed(f"Redis failed ({type(error).__name__})") from error
        return denial_id

    async def denial(self, denial_id: str) -> DeniedSignInOut | None:
        """The account turned away under `denial_id`; None once it expired or when Redis
        fails (the sign-in page then just does not name it)."""
        try:
            value = await self._redis.get(_key("denied", denial_id))
        except (RedisError, OSError) as error:
            logger.warning(
                "Redis failed (%s): the denied sign-in is not known", type(error).__name__
            )
            return None
        return None if value is None else DeniedSignInOut.model_validate_json(value)
