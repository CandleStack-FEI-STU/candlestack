"""What the routes of every module depend on to know the signed-in user, and the sign-in rate
limit."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request, Response

from candlestack.accounts.cookies import SESSION, Cookies, CookiesDep
from candlestack.accounts.models import User
from candlestack.accounts.oauth import OAuthClient
from candlestack.accounts.pending import PendingStore
from candlestack.accounts.service import SESSION_MAX_AGE, AccountDeletionHook, AccountsService
from candlestack.accounts.store import AccountStore
from candlestack.core import (
    DbSessionDep,
    HttpClientDep,
    ProblemError,
    RateLimiterDep,
    RedisDep,
    SettingsDep,
    client_address,
)

# Sign-in requests (start, callback, dev sign-in) per minute and client address: a person needs
# a few; more is someone trying states or codes.
SIGN_IN_RATE_LIMIT = 20


def get_deletion_hooks(request: Request) -> Sequence[AccountDeletionHook]:
    """What else goes with a deleted account: the hooks ``candlestack.main`` puts on the app."""
    return request.app.state.account_deletion_hooks


def get_accounts_service(
    settings: SettingsDep,
    redis: RedisDep,
    db: DbSessionDep,
    http: HttpClientDep,
    deletion_hooks: Annotated[Sequence[AccountDeletionHook], Depends(get_deletion_hooks)],
) -> AccountsService:
    return AccountsService(
        settings,
        AccountStore(db),
        PendingStore(redis),
        OAuthClient(settings, http),
        deletion_hooks=deletion_hooks,
    )


AccountsServiceDep = Annotated[AccountsService, Depends(get_accounts_service)]


@dataclass(frozen=True, slots=True)
class BrowserSession:
    """The session whose cookie came with a request: its token and user."""

    token: str
    user: User
    extended: bool
    cookies: Cookies

    def slide_on(self, response: Response) -> None:
        """Sends the cookie again with the new expiry on `response` when the session was just
        extended, so a session in use slides on. Every response to a signed-in browser
        passes here."""
        if self.extended:
            self.cookies.set(response, SESSION, self.token, SESSION_MAX_AGE)


async def browser_session(
    request: Request, service: AccountsService, cookies: Cookies
) -> BrowserSession | None:
    """The session whose cookie came with the request; None without a cookie, or when its
    session ended. Looking it up may extend it: the caller sends the response it returns
    through `BrowserSession.slide_on`."""
    token = cookies.read(request, SESSION)
    signed_in = None if token is None else await service.signed_in(token)
    if token is None or signed_in is None:
        return None
    return BrowserSession(token, signed_in.user, signed_in.extended, cookies)


async def current_user(
    request: Request, response: Response, service: AccountsServiceDep, cookies: CookiesDep
) -> User:
    """The user whose session cookie came with the request; 401 ``not-signed-in`` without one.

    The session slides on through the response FastAPI builds from what the route returns. A
    route that returns a ``Response`` of its own loses that cookie, so routes of the signed-in
    user return their data.
    """
    session = await browser_session(request, service, cookies)
    if session is None:
        raise ProblemError(
            401,
            "not-signed-in",
            "Not signed in",
            "This needs a signed-in user, and the request has no session or its session ended. "
            "Sign in again.",
        )
    session.slide_on(response)
    return session.user


CurrentUserDep = Annotated[User, Depends(current_user)]


async def sign_in_wait(request: Request, limiter: RateLimiterDep) -> int:
    """Counts a sign-in request of the client; the seconds it must wait, 0 within the limit."""
    wait = await limiter.hit(f"accounts:rl:{client_address(request)}", SIGN_IN_RATE_LIMIT)
    return max(1, math.ceil(wait)) if wait > 0 else 0


async def limit_sign_ins(wait: Annotated[int, Depends(sign_in_wait)]) -> None:
    """429 ``rate-limited`` beyond ``SIGN_IN_RATE_LIMIT`` sign-in requests a minute."""
    if wait:
        raise ProblemError(
            429,
            "rate-limited",
            "Too many requests",
            f"More than {SIGN_IN_RATE_LIMIT} sign-in requests in one minute from this address. "
            f"Retry in {wait} seconds.",
            headers={"Retry-After": str(wait)},
            extensions={"limit": SIGN_IN_RATE_LIMIT},
        )
