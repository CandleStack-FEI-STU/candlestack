"""Accounts: users, GitHub and Google sign-in, sessions and the beta list.

Other modules import only from here (``from candlestack.accounts import CurrentUserDep``),
never from the submodules. A route of the signed-in user takes ``user: CurrentUserDep``, and
one that changes something also depends on ``core.require_same_origin``.
"""

from candlestack.accounts.api import dev_router as dev_sign_in_router
from candlestack.accounts.api import dev_sign_in_allowed
from candlestack.accounts.api import router as accounts_router
from candlestack.accounts.dependencies import CurrentUserDep
from candlestack.accounts.models import User
from candlestack.accounts.schemas import DeniedSignInOut, MeOut, Provider

__all__ = [
    "CurrentUserDep",
    "DeniedSignInOut",
    "MeOut",
    "Provider",
    "User",
    "accounts_router",
    "dev_sign_in_allowed",
    "dev_sign_in_router",
]
