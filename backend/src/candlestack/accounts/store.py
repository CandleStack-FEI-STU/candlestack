"""The accounts tables in Postgres: the queries the service needs, in the request's session.
Nothing here commits; the service does, once a change is complete."""

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession

from candlestack.accounts.models import Identity, User, UserPreferences, UserSession


class AccountStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @property
    def db(self) -> AsyncSession:
        """The request's session, for the account deletion hooks of other modules."""
        return self._db

    def add(self, row: User | Identity | UserSession) -> None:
        self._db.add(row)

    async def commit(self) -> None:
        await self._db.commit()

    async def identity(self, provider: str, subject: str) -> Identity | None:
        return await self._db.get(Identity, (provider, subject))

    async def user(self, user_id: str) -> User | None:
        return await self._db.get(User, user_id)

    async def lock_user(self, user_id: str) -> None:
        """Locks the user's row until the commit, so changes of their sign-in methods run one
        after the other."""
        await self._db.execute(select(User.id).where(User.id == user_id).with_for_update())

    async def user_by_email(self, email: str) -> User | None:
        return await self._db.scalar(select(User).where(User.email == email))

    async def delete_user(self, user_id: str) -> None:
        """Deletes the user; their identities, sessions and preferences go with them (the
        foreign keys cascade)."""
        await self._db.execute(delete(User).where(User.id == user_id))

    async def providers(self, user_id: str) -> list[str]:
        """The providers the user signs in with, in alphabetical order."""
        rows = await self._db.scalars(
            select(Identity.provider).where(Identity.user_id == user_id).order_by(Identity.provider)
        )
        return list(rows)

    async def delete_identities(self, user_id: str, provider: str) -> None:
        await self._db.execute(
            delete(Identity).where(Identity.user_id == user_id, Identity.provider == provider)
        )

    async def session(self, token_hash: bytes) -> tuple[UserSession, User] | None:
        row = (
            await self._db.execute(
                select(UserSession, User)
                .join(User, User.id == UserSession.user_id)
                .where(UserSession.token_hash == token_hash)
            )
        ).first()
        return None if row is None else (row[0], row[1])

    async def delete_session(self, token_hash: bytes) -> None:
        await self._db.execute(delete(UserSession).where(UserSession.token_hash == token_hash))

    async def delete_sessions(self, user_id: str) -> None:
        await self._db.execute(delete(UserSession).where(UserSession.user_id == user_id))

    async def delete_expired_sessions(self, user_id: str, now: datetime) -> None:
        await self._db.execute(
            delete(UserSession).where(UserSession.user_id == user_id, UserSession.expires_at <= now)
        )

    async def preferences(self, user_id: str) -> UserPreferences | None:
        return await self._db.get(UserPreferences, user_id)

    async def save_backtest_defaults(
        self, user_id: str, document: dict[str, Any], now: datetime
    ) -> None:
        """Replaces the user's backtest defaults with `document`."""
        new = insert(UserPreferences).values(
            user_id=user_id, backtest_defaults=document, updated_at=now
        )
        await self._db.execute(
            new.on_conflict_do_update(
                index_elements=[UserPreferences.user_id],
                set_={"backtest_defaults": new.excluded.backtest_defaults, "updated_at": now},
            )
        )

    async def merge_appearance(
        self, user_id: str, changes: dict[str, Any], now: datetime
    ) -> dict[str, Any]:
        """Merges `changes` into the user's appearance document in one statement, so changes
        sent at the same time all stay; returns the merged document."""
        new = insert(UserPreferences).values(user_id=user_id, appearance=changes, updated_at=now)
        merged = await self._db.scalar(
            new.on_conflict_do_update(
                index_elements=[UserPreferences.user_id],
                set_={
                    "appearance": UserPreferences.appearance.op("||", return_type=JSONB)(
                        new.excluded.appearance
                    ),
                    "updated_at": now,
                },
            ).returning(UserPreferences.appearance)
        )
        assert merged is not None  # an upsert returns its row
        return merged
