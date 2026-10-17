"""What the routes of every module depend on to know the signed-in user, and the sign-in rate
limit."""

import math
from typing import Annotated

from fastapi import Depends, Request, Response

from candlestack.accounts.cookies import SESSION, CookiesDep
from candlestack.accounts.models import User
from candlestack.accounts.oauth import OAuthClient
from candlestack.accounts.pending import PendingStore
from candlestack.accounts.service import SESSION_MAX_AGE, AccountsService
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


def get_accounts_service(
    settings: SettingsDep, redis: RedisDep, db: DbSessionDep, http: HttpClientDep
) -> AccountsService:
    return AccountsService(
        settings, AccountStore(db), PendingStore(redis), OAuthClient(settings, http)
    )


AccountsServiceDep = Annotated[AccountsService, Depends(get_accounts_service)]


async def current_user(
    request: Request, response: Response, service: AccountsServiceDep, cookies: CookiesDep
) -> User:
    """The user whose session cookie came with the request; 401 ``not-signed-in`` without one.

    A session in use slides on: when the service extends it, the cookie goes out again with
    the new expiry, on the response FastAPI builds from what the route returns. A route that
    returns a ``Response`` of its own loses that cookie, so routes of the signed-in user
    return their data.
    """
    token = cookies.read(request, SESSION)
    signed_in = None if token is None else await service.signed_in(token)
    if token is None or signed_in is None:
        raise ProblemError(
            401,
            "not-signed-in",
            "Not signed in",
            "This needs a signed-in user, and the request has no session or its session ended. "
            "Sign in again.",
        )
    if signed_in.extended:
        cookies.set(response, SESSION, token, SESSION_MAX_AGE)
    return signed_in.user


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
