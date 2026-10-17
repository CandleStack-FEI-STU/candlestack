"""The accounts tables in Postgres: the queries the service needs, in the request's session.
Nothing here commits; the service does, once a change is complete."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from candlestack.accounts.models import Identity, User, UserSession


class AccountStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def add(self, row: User | Identity | UserSession) -> None:
        self._db.add(row)

    async def commit(self) -> None:
        await self._db.commit()

    async def identity(self, provider: str, subject: str) -> Identity | None:
        return await self._db.get(Identity, (provider, subject))

    async def user(self, user_id: str) -> User | None:
        return await self._db.get(User, user_id)

    async def user_by_email(self, email: str) -> User | None:
        return await self._db.scalar(select(User).where(User.email == email))

    async def providers(self, user_id: str) -> list[str]:
        """The providers the user signs in with, in alphabetical order."""
        rows = await self._db.scalars(
            select(Identity.provider).where(Identity.user_id == user_id).order_by(Identity.provider)
        )
        return list(rows)

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

    async def delete_expired_sessions(self, user_id: str, now: datetime) -> None:
        await self._db.execute(
            delete(UserSession).where(UserSession.user_id == user_id, UserSession.expires_at <= now)
        )
