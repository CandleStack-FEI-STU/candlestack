"""Signing in and out: the OAuth round trip, the beta list, accounts and sessions.

A sign-in starts with a random ``state`` kept in Redis (with the PKCE verifier and where to go
next) and in a cookie of the browser; the callback must bring back both, so nobody can finish a
sign-in that another browser started (login CSRF). The account the provider vouches for signs
in only when its email is on the beta list. A session is a random token in the browser's cookie;
Postgres keeps only its SHA-256.
"""

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from candlestack.accounts.errors import SignInDenied, SignInFailed
from candlestack.accounts.models import Identity, User, UserSession, new_user_id
from candlestack.accounts.oauth import OAuthClient, ProviderAccount
from candlestack.accounts.pending import PendingSignIn, PendingStore
from candlestack.accounts.schemas import DeniedSignInOut, MeOut, Provider
from candlestack.accounts.store import AccountStore
from candlestack.core import Settings

DEFAULT_NEXT = "/dashboard"
SESSION_LIFETIME = timedelta(days=30)
SESSION_MAX_AGE = int(SESSION_LIFETIME.total_seconds())
# A session in use is extended at most this often, so a busy user costs one write a day.
SESSION_REFRESH = timedelta(days=1)
# The fixed account of the dev sign-in (local runs and tests only).
DEV_EMAIL = "dev@candlestack.tech"
DEV_NAME = "Dev user"
# Longer values than the app ever sends are not looked up.
_MAX_STATE = 64
_MAX_NEXT = 2048
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _now() -> datetime:
    """The time; patched by tests to move the clock."""
    return datetime.now(UTC)


def safe_next(path: str | None) -> str:
    """`path` when it is a page of the app, else ``/dashboard``: never another site (``//host``,
    a backslash, ``https://...``) and never the API."""
    if (
        not path
        or len(path) > _MAX_NEXT
        or not path.startswith("/")
        or path.startswith(("//", "/api/", "/api?", "/api#"))
        or path == "/api"
        or "\\" in path
        or _CONTROL.search(path)
    ):
        return DEFAULT_NEXT
    return path


def _hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


@dataclass(frozen=True, slots=True)
class SignInStart:
    """Where to send the browser, and the state to put in its cookie."""

    url: str
    state: str


@dataclass(frozen=True, slots=True)
class SignInDone:
    """The page to open, and the token of the new session to put in the browser's cookie."""

    next_path: str
    session_token: str


@dataclass(frozen=True, slots=True)
class SignedIn:
    """The user of a session; ``extended`` when the cookie must be sent again to slide on."""

    user: User
    extended: bool


class AccountsService:
    def __init__(
        self, settings: Settings, store: AccountStore, pending: PendingStore, oauth: OAuthClient
    ) -> None:
        self._settings = settings
        self._store = store
        self._pending = pending
        self._oauth = oauth

    async def start_sign_in(self, provider: Provider, next_path: str | None) -> SignInStart:
        """Where to send the browser to sign in with `provider`, and the state for its cookie.

        Raises:
            SignInFailed: The provider is not configured, or Redis failed.
        """
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        url = self._oauth.authorization_url(provider, state=state, verifier=verifier)
        await self._pending.put_sign_in(
            state, PendingSignIn(provider=provider, verifier=verifier, next=safe_next(next_path))
        )
        return SignInStart(url=url, state=state)

    async def finish_sign_in(
        self,
        provider: Provider,
        *,
        state: str | None,
        browser_state: str | None,
        code: str | None,
        error: str | None,
    ) -> SignInDone:
        """Signs in the account the provider returned with.

        `state`, `code` and `error` are the callback's query parameters, `browser_state` the
        state cookie of the browser.

        Raises:
            SignInFailed: The sign-in was cancelled or failed.
            SignInDenied: The account's email is not on the beta list.
        """
        if not state or not browser_state or len(state) > _MAX_STATE:
            raise SignInFailed("the state is missing or too long")
        if not secrets.compare_digest(state.encode(), browser_state.encode()):
            raise SignInFailed("the state does not match this browser's")
        pending = await self._pending.take_sign_in(state)
        if pending is None or pending.provider is not provider:
            raise SignInFailed("the state is unknown or expired")
        if error is not None or not code:
            raise SignInFailed(f"{provider} returned no code (cancelled or refused)")
        account = await self._oauth.fetch_account(provider, code=code, verifier=pending.verifier)
        if account.email not in self._settings.beta_allowlist:
            raise SignInDenied(await self._pending.put_denial(account.email, provider))
        user = await self._account_of(account)
        return SignInDone(next_path=pending.next, session_token=await self._new_session(user))

    async def _account_of(self, account: ProviderAccount) -> User:
        """The user `account` signs in as: the one it signed in as before, else the one with
        its email, else a new one."""
        now = _now()
        identity = await self._store.identity(account.provider, account.subject)
        if identity is not None:
            identity.email = account.email
            identity.login = account.login
            user = await self._store.user(identity.user_id)
            assert user is not None  # the foreign key
        else:
            user = await self._store.user_by_email(account.email)
            if user is None:
                user = self._new_user(account.email, _display_name(account), now)
            self._store.add(
                Identity(
                    provider=account.provider,
                    subject=account.subject,
                    user=user,
                    email=account.email,
                    login=account.login,
                    created_at=now,
                )
            )
        user.last_sign_in_at = now
        return user

    def _new_user(self, email: str, display_name: str, now: datetime) -> User:
        user = User(
            id=new_user_id(),
            display_name=display_name,
            email=email,
            created_at=now,
            last_sign_in_at=now,
        )
        self._store.add(user)
        return user

    async def dev_sign_in(self) -> str:
        """Signs in as the fixed dev user, without a provider or the beta list; returns the
        session's token."""
        now = _now()
        user = await self._store.user_by_email(DEV_EMAIL)
        if user is None:
            user = self._new_user(DEV_EMAIL, DEV_NAME, now)
        user.last_sign_in_at = now
        return await self._new_session(user)

    async def _new_session(self, user: User) -> str:
        """Starts a session of `user`, commits the sign-in and returns the session's token; the
        user's expired sessions go."""
        now = _now()
        token = secrets.token_urlsafe(32)
        await self._store.delete_expired_sessions(user.id, now)
        self._store.add(
            UserSession(
                token_hash=_hash(token),
                user=user,
                created_at=now,
                last_seen_at=now,
                expires_at=now + SESSION_LIFETIME,
            )
        )
        await self._store.commit()
        return token

    async def signed_in(self, token: str) -> SignedIn | None:
        """The user of the session with `token`; None when there is none or it expired (an
        expired one is deleted). A session last extended a day or more ago is extended."""
        found = await self._store.session(_hash(token))
        if found is None:
            return None
        session, user = found
        now = _now()
        if session.expires_at <= now:
            await self._store.delete_session(session.token_hash)
            await self._store.commit()
            return None
        extended = now - session.last_seen_at >= SESSION_REFRESH
        if extended:
            session.last_seen_at = now
            session.expires_at = now + SESSION_LIFETIME
            await self._store.commit()
        return SignedIn(user=user, extended=extended)

    async def sign_out(self, token: str) -> None:
        await self._store.delete_session(_hash(token))
        await self._store.commit()

    async def me(self, user: User) -> MeOut:
        providers = await self._store.providers(user.id)
        return MeOut(
            id=user.id,
            display_name=user.display_name,
            email=user.email,
            providers=[Provider(provider) for provider in providers],
            created_at=user.created_at,
        )

    async def denial(self, denial_id: str) -> DeniedSignInOut | None:
        return await self._pending.denial(denial_id)


def _display_name(account: ProviderAccount) -> str:
    """GitHub's name or else login, Google's name, else the email's local part."""
    return account.name or account.login or account.email.partition("@")[0]
