"""The accounts tables: users, the GitHub and Google identities they sign in with, and their
browser sessions. Changed only through migrations (``backend/migrations``)."""

import secrets
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from candlestack.core import Base

# Lowercase RFC 4648 base32: no 0, 1, 8 or 9, so an ID read aloud or typed cannot mix up
# similar characters.
_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyz234567"
_ID_LENGTH = 10


def new_user_id() -> str:
    """A public user ID such as ``usr_7f3k2m9qx4`` (50 random bits)."""
    return "usr_" + "".join(secrets.choice(_ID_ALPHABET) for _ in range(_ID_LENGTH))


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(14), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200))
    # Lowercased, so the same address from another provider finds the account.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_sign_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Identity(Base):
    """An account at GitHub or Google that signs in as a user: the provider's own ID of the
    account (``subject``), which stays when its email or login changes, names it."""

    __tablename__ = "identities"

    provider: Mapped[str] = mapped_column(String(16), primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    login: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Never loaded implicitly (that would be I/O on attribute access): only set, so a new
    # identity and its new user are inserted in the right order.
    user: Mapped[User] = relationship(lazy="raise")


class UserSession(Base):
    """A signed-in browser. Only the SHA-256 of the cookie's token is stored, so the table
    cannot be used to sign in."""

    __tablename__ = "sessions"

    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="raise")
