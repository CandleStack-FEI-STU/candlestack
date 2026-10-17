"""HTTP API of the accounts module: ``/api/v1/auth/...`` and ``/api/v1/me``.

Sign-in starts at ``GET /api/v1/auth/{provider}/start?next=<path>``, which redirects to GitHub
or Google; the provider returns to ``/api/v1/auth/{provider}/callback``, which sets the session
cookie and redirects to ``next`` (default ``/dashboard``), or to ``/signin?error=denied`` (not on
the beta list: ``GET /api/v1/auth/denied`` names the account) or ``/signin?error=failed``.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse

from candlestack.accounts.cookies import DENIED, SESSION, STATE, CookiesDep
from candlestack.accounts.dependencies import (
    AccountsServiceDep,
    CurrentUserDep,
    limit_sign_ins,
    sign_in_wait,
)
from candlestack.accounts.errors import SignInDenied, SignInFailed
from candlestack.accounts.pending import TTL
from candlestack.accounts.schemas import (
    Appearance,
    AppearanceUpdate,
    BacktestDefaults,
    DeniedSignInOut,
    MeOut,
    MeUpdate,
    PreferencesOut,
    Provider,
    SignInIntent,
)
from candlestack.accounts.service import SESSION_MAX_AGE
from candlestack.core import DATABASE_ERRORS, Problem, ProblemError, require_same_origin

logger = logging.getLogger(__name__)

router = APIRouter(tags=["accounts"])

FAILED_URL = "/signin?error=failed"
DENIED_URL = "/signin?error=denied"
# What the responses about the user carry must not be kept by a browser cache or a proxy.
NO_STORE = {"Cache-Control": "no-store"}
# Environments with the dev sign-in: never stage or prod, whatever their settings say.
_DEV_SIGN_IN_ENVS = frozenset({"local", "test"})

IntentParam = Annotated[
    SignInIntent,
    Query(description="`sign-in` (default), or `connect` to add a sign-in method in Settings"),
]

NextPath = Annotated[
    str | None,
    Query(
        description="Path of the app to open after signing in (default `/dashboard`)",
        examples=["/dashboard"],
    ),
]


def _problem(status: int, description: str) -> dict[int | str, dict[str, Any]]:
    """An OpenAPI error response of a route: a problem with the given description."""
    return {status: {"model": Problem, "description": description}}


def dev_sign_in_allowed(app_env: str) -> bool:
    return app_env in _DEV_SIGN_IN_ENVS


def _failed(provider: Provider, error: SignInFailed) -> RedirectResponse:
    logger.warning("Sign-in with %s failed: %s", provider, error.reason)
    return RedirectResponse(FAILED_URL, status_code=302)


@router.get(
    "/api/v1/auth/{provider}/start",
    status_code=302,
    response_class=RedirectResponse,
)
async def start_sign_in(  # noqa: PLR0917 (scaffold: the builder makes intent keyword-only)
    provider: Provider,
    service: AccountsServiceDep,
    cookies: CookiesDep,
    wait: Annotated[int, Depends(sign_in_wait)],
    next: NextPath = None,  # noqa: A002 (the parameter's name in the URL)
    intent: IntentParam = SignInIntent.sign_in,  # noqa: ARG001 (scaffold)
) -> RedirectResponse:
    """Redirects to the provider's sign-in page, or to `/signin?error=failed` when sign-in
    with it is not available or this address made too many sign-in requests in a minute.

    With `intent=connect` (signed in, from Settings) the provider's account is added to the
    signed-in user's sign-in methods instead: the callback returns to `next` (default
    `/settings/sign-in`), or to `/settings/sign-in?error=taken` when that account already
    signs in to another CandleStack user, or `/settings/sign-in?error=failed`."""
    try:
        if wait:
            raise SignInFailed("too many sign-in requests from this address")
        start = await service.start_sign_in(provider, next)
    except SignInFailed as error:
        return _failed(provider, error)
    response = RedirectResponse(start.url, status_code=302)
    cookies.set(response, STATE, start.state, TTL)
    return response


@router.get("/api/v1/auth/{provider}/callback", include_in_schema=False)
async def finish_sign_in(  # noqa: PLR0913 (the provider's query parameters)
    provider: Provider,
    *,
    request: Request,
    service: AccountsServiceDep,
    cookies: CookiesDep,
    wait: Annotated[int, Depends(sign_in_wait)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    try:
        if wait:
            raise SignInFailed("too many sign-in requests from this address")
        done = await service.finish_sign_in(
            provider,
            state=state,
            browser_state=cookies.read(request, STATE),
            code=code,
            error=error,
        )
    except SignInDenied as denied:
        response = RedirectResponse(DENIED_URL, status_code=302)
        cookies.set(response, DENIED, denied.denial_id, TTL)
    except SignInFailed as failed:
        response = _failed(provider, failed)
    except DATABASE_ERRORS as failed:
        # Postgres is down, or another first sign-in of the same account was just saved. The
        # browser comes back from the provider, so it gets the sign-in page, not a problem. The
        # error reaches Sentry by its type only: its message and the variables of its frames
        # may hold the account's email.
        logger.error(
            "Sign-in with %s failed: Postgres failed (%s)", provider, type(failed).__name__
        )
        response = RedirectResponse(FAILED_URL, status_code=302)
    else:
        response = RedirectResponse(done.next_path, status_code=302)
        cookies.set(response, SESSION, done.session_token, SESSION_MAX_AGE)
    cookies.delete(response, STATE)
    return response


@router.post(
    "/api/v1/auth/sign-out",
    status_code=204,
    responses=_problem(
        403, "The request does not come from the app's own pages (`cross-origin-request`)."
    ),
    dependencies=[Depends(require_same_origin)],
)
async def sign_out(request: Request, service: AccountsServiceDep, cookies: CookiesDep) -> Response:
    """Ends this browser's session; 204 also when it had none."""
    token = cookies.read(request, SESSION)
    if token is not None:
        await service.sign_out(token)
    response = Response(status_code=204)
    cookies.delete(response, SESSION)
    return response


@router.get(
    "/api/v1/auth/denied",
    responses=_problem(404, "This browser was not turned away lately (`not-found`)."),
)
async def denied_sign_in(
    request: Request, response: Response, service: AccountsServiceDep, cookies: CookiesDep
) -> DeniedSignInOut:
    """The account the beta list just turned away, for the sign-in page; 404 when this browser
    was not turned away in the last 10 minutes."""
    denial_id = cookies.read(request, DENIED)
    denied = await service.denial(denial_id) if denial_id else None
    if denied is None:
        raise ProblemError(
            404,
            "not-found",
            "Not Found",
            "This browser was not turned away by the beta list in the last 10 minutes.",
        )
    response.headers.update(NO_STORE)
    return denied


@router.get(
    "/api/v1/me",
    responses=_problem(401, "No session came with the request, or it ended (`not-signed-in`)."),
)
async def me(user: CurrentUserDep, service: AccountsServiceDep, response: Response) -> MeOut:
    """The signed-in user."""
    response.headers.update(NO_STORE)
    return await service.me(user)


# Registered only where ``dev_sign_in_allowed``; hidden from the API reference.
dev_router = APIRouter(include_in_schema=False)


@dev_router.post(
    "/api/v1/auth/dev",
    status_code=204,
    dependencies=[Depends(require_same_origin), Depends(limit_sign_ins)],
)
async def dev_sign_in(service: AccountsServiceDep, cookies: CookiesDep) -> Response:
    """Signs this browser in as the dev user, so the app can be tried without OAuth keys."""
    response = Response(status_code=204)
    cookies.set(response, SESSION, await service.dev_sign_in(), SESSION_MAX_AGE)
    return response


# --- M2: settings (contract; the bodies come with the implementation) ---------------------


@router.patch(
    "/api/v1/me",
    responses=_problem(401, "Not signed in (`not-signed-in`)."),
    dependencies=[Depends(require_same_origin)],
)
async def update_me(body: MeUpdate, user: CurrentUserDep) -> MeOut:
    """Changes the display name."""
    raise NotImplementedError


@router.delete(
    "/api/v1/me",
    status_code=204,
    responses=_problem(401, "Not signed in (`not-signed-in`)."),
    dependencies=[Depends(require_same_origin)],
)
async def delete_me(user: CurrentUserDep) -> Response:
    """Deletes the account with everything it owns and ends all its sessions."""
    raise NotImplementedError


@router.delete(
    "/api/v1/me/sign-in-methods/{provider}",
    status_code=204,
    responses=_problem(409, "It is the account's last sign-in method (`last-sign-in-method`)."),
    dependencies=[Depends(require_same_origin)],
)
async def disconnect(provider: Provider, user: CurrentUserDep) -> Response:
    """Removes a sign-in method; the last one cannot be removed."""
    raise NotImplementedError


@router.post(
    "/api/v1/auth/sign-out-everywhere",
    status_code=204,
    responses=_problem(401, "Not signed in (`not-signed-in`)."),
    dependencies=[Depends(require_same_origin)],
)
async def sign_out_everywhere(user: CurrentUserDep) -> Response:
    """Ends every session of the user, this one included."""
    raise NotImplementedError


@router.get("/api/v1/me/preferences", responses=_problem(401, "Not signed in (`not-signed-in`)."))
async def preferences(user: CurrentUserDep) -> PreferencesOut:
    """The user's settings, defaults included."""
    raise NotImplementedError


@router.put(
    "/api/v1/me/preferences/backtest-defaults",
    responses=_problem(401, "Not signed in (`not-signed-in`)."),
    dependencies=[Depends(require_same_origin)],
)
async def save_backtest_defaults(body: BacktestDefaults, user: CurrentUserDep) -> BacktestDefaults:
    """Saves how new backtests start (Save defaults)."""
    raise NotImplementedError


@router.patch(
    "/api/v1/me/preferences/appearance",
    responses=_problem(401, "Not signed in (`not-signed-in`)."),
    dependencies=[Depends(require_same_origin)],
)
async def update_appearance(body: AppearanceUpdate, user: CurrentUserDep) -> Appearance:
    """Changes some appearance settings; each control saves as soon as it changes."""
    raise NotImplementedError
