"""What a sign-in does when Redis fails; the round trips through a real Redis are integration
tests (tests/integration/accounts)."""

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, cast

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from candlestack.accounts.errors import SignInFailed
from candlestack.accounts.pending import PendingSignIn, PendingStore
from candlestack.accounts.schemas import Provider

if TYPE_CHECKING:
    from redis.asyncio import Redis

pytestmark = pytest.mark.anyio


class DownRedis:
    """A Redis client whose server is down: every command fails."""

    def __getattr__(self, _command: str) -> Callable[..., Awaitable[None]]:
        async def fail(*_args: object, **_kwargs: object) -> None:
            raise RedisConnectionError("Connection refused")

        return fail


@pytest.fixture
def pending() -> PendingStore:
    return PendingStore(cast("Redis", DownRedis()))


async def test_a_sign_in_cannot_start(pending: PendingStore) -> None:
    sign_in = PendingSignIn(provider=Provider.github, verifier="v", next="/dashboard")

    with pytest.raises(SignInFailed, match="Redis failed"):
        await pending.put_sign_in("state", sign_in)


async def test_a_sign_in_cannot_finish(pending: PendingStore) -> None:
    with pytest.raises(SignInFailed, match="Redis failed"):
        await pending.take_sign_in("state")


async def test_a_denial_cannot_be_kept(pending: PendingStore) -> None:
    with pytest.raises(SignInFailed, match="Redis failed"):
        await pending.put_denial("ada@example.com", Provider.github)


async def test_a_denial_is_not_known(
    pending: PendingStore, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        assert await pending.denial("id") is None

    assert "Redis failed (ConnectionError)" in caplog.text
