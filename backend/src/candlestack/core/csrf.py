"""Cross-site request forgery protection for the requests a session cookie authenticates.

SameSite=Lax keeps the session cookie off requests that other sites start, except top-level
navigations, but every host under candlestack.tech is the same site to the browser, so a page on any
of them could post to prod with the cookie. So every route that changes something on behalf of
the signed-in user requires the request to come from the app's own origin, by the browser's
``Origin`` header or, without one, ``Sec-Fetch-Site: same-origin``:
``@router.post(..., dependencies=[Depends(require_same_origin)])``.
"""

from fastapi import Request

from candlestack.core.config import SettingsDep
from candlestack.core.errors import ProblemError


def require_same_origin(request: Request, settings: SettingsDep) -> None:
    """403 ``cross-origin-request`` unless the request comes from a page of ``PUBLIC_URL``."""
    origin = request.headers.get("origin")
    if origin is not None:
        same = origin == settings.public_url
    else:
        same = request.headers.get("sec-fetch-site") == "same-origin"
    if not same:
        raise ProblemError(
            403,
            "cross-origin-request",
            "Cross-origin request",
            "This request changes your account, so it is accepted only from the CandleStack app "
            f"at {settings.public_url}. Open the app there and try again.",
        )
