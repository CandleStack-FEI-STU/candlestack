"""The two phases of deleting an account: the deletion hooks in its transaction, and what they
return after the commit. Over HTTP with a real Postgres: tests/integration/accounts."""

import logging
from typing import TYPE_CHECKING, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from candlestack.accounts.models import User
from candlestack.accounts.service import AccountDeletionHook, AccountsService, AfterDeletion
from candlestack.core import Settings

if TYPE_CHECKING:
    from candlestack.accounts.oauth import OAuthClient
    from candlestack.accounts.pending import PendingStore
    from candlestack.accounts.store import AccountStore

pytestmark = pytest.mark.anyio

USER = User(id="usr_7f3k2m9qx4")
DB = cast("AsyncSession", object())


class FakeStore:
    """Records the deletion's steps in `events`; its commit fails when told to."""

    def __init__(self, events: list[str], *, commit_fails: bool = False) -> None:
        self.events = events
        self.db = DB
        self._commit_fails = commit_fails

    async def delete_user(self, user_id: str) -> None:
        self.events.append(f"delete {user_id}")

    async def commit(self) -> None:
        if self._commit_fails:
            raise ConnectionError("Postgres went away")
        self.events.append("commit")


def service(store: FakeStore, *hooks: AccountDeletionHook) -> AccountsService:
    return AccountsService(
        Settings(),
        cast("AccountStore", store),
        cast("PendingStore", None),
        cast("OAuthClient", None),
        deletion_hooks=hooks,
    )


def hook(events: list[str], name: str, *, after: str | None = None) -> AccountDeletionHook:
    """A hook that records its call and, with `after`, returns what records `after`."""

    async def run_after() -> None:
        events.append(after or "")

    async def call(user_id: str, db: AsyncSession) -> AfterDeletion | None:
        assert db is DB  # the deletion's transaction
        events.append(f"{name} {user_id}")
        return run_after if after is not None else None

    return call


def failing_after(events: list[str]) -> AccountDeletionHook:
    async def run_after() -> None:
        events.append("failing after")
        raise OSError("cannot remove /data/models/ada@example.com/model.keras")

    async def call(_user_id: str, _db: AsyncSession) -> AfterDeletion:
        return run_after

    return call


async def test_the_hooks_run_before_the_delete_and_their_after_once_it_is_committed() -> None:
    events: list[str] = []
    store = FakeStore(events)
    accounts = service(
        store,
        hook(events, "models", after="model files"),
        hook(events, "backtests"),  # rows only
        hook(events, "exports", after="export files"),
    )

    await accounts.delete_account(USER)

    assert events == [
        "models usr_7f3k2m9qx4",
        "backtests usr_7f3k2m9qx4",
        "exports usr_7f3k2m9qx4",
        "delete usr_7f3k2m9qx4",
        "commit",
        "model files",
        "export files",
    ]


async def test_a_failing_hook_stops_the_deletion() -> None:
    events: list[str] = []

    async def failing(_user_id: str, _db: AsyncSession) -> AfterDeletion | None:
        raise RuntimeError("the backtests could not be deleted")

    accounts = service(FakeStore(events), hook(events, "models", after="model files"), failing)

    with pytest.raises(RuntimeError):
        await accounts.delete_account(USER)

    # Nothing outside Postgres was touched: the files of the models stay with the account.
    assert events == ["models usr_7f3k2m9qx4"]


async def test_nothing_runs_after_a_failed_commit() -> None:
    events: list[str] = []
    accounts = service(
        FakeStore(events, commit_fails=True), hook(events, "models", after="model files")
    )

    with pytest.raises(ConnectionError):
        await accounts.delete_account(USER)

    assert events == ["models usr_7f3k2m9qx4", "delete usr_7f3k2m9qx4"]


async def test_a_failure_after_the_commit_is_logged_and_the_rest_still_run(caplog) -> None:
    events: list[str] = []
    accounts = service(
        FakeStore(events), failing_after(events), hook(events, "exports", after="export files")
    )

    with caplog.at_level(logging.ERROR):
        await accounts.delete_account(USER)

    assert events[-3:] == ["commit", "failing after", "export files"]
    assert "Deleting an account's data after the commit failed (OSError)" in caplog.text
    # By its type only: the message may hold the user's data.
    assert "ada@example.com" not in caplog.text
    assert [record.exc_info for record in caplog.records] == [None]
