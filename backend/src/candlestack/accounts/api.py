"""HTTP API of the accounts module: ``/api/v1/auth/...`` and ``/api/v1/me``.

Contract (scaffold): sign-in starts at ``GET /api/v1/auth/{provider}/start?next=<path>``, which
redirects to GitHub or Google; the provider returns to ``/api/v1/auth/{provider}/callback``,
which sets the session cookie and redirects to ``next`` (default ``/dashboard``), or to
``/signin?error=denied`` (not on the beta list: ``GET /api/v1/auth/denied`` names the account)
or ``/signin?error=failed``.
"""

from typing import Annotated

from fastapi import APIRouter, Query, Response
from fastapi.responses import RedirectResponse

from candlestack.accounts.schemas import DeniedSignInOut, MeOut, Provider

router = APIRouter(tags=["accounts"])

NextPath = Annotated[
    str | None,
    Query(
        description="Path of the app to open after signing in (default `/dashboard`)",
        examples=["/dashboard"],
    ),
]


@router.get("/api/v1/auth/{provider}/start", status_code=302, response_class=RedirectResponse)
async def start_sign_in(provider: Provider, next: NextPath = None) -> RedirectResponse:  # noqa: A002
    """Redirects to the provider's sign-in page."""
    raise NotImplementedError


@router.get("/api/v1/auth/{provider}/callback", include_in_schema=False)
async def finish_sign_in(provider: Provider) -> RedirectResponse:
    raise NotImplementedError


@router.post("/api/v1/auth/sign-out", status_code=204)
async def sign_out() -> Response:
    """Ends this browser's session."""
    raise NotImplementedError


@router.get("/api/v1/auth/denied")
async def denied_sign_in() -> DeniedSignInOut:
    """The account the beta list just turned away, for the sign-in page."""
    raise NotImplementedError


@router.get("/api/v1/me")
async def me() -> MeOut:
    """The signed-in user."""
    raise NotImplementedError
