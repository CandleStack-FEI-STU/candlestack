"""Why a sign-in ended without a session. The API turns both into a redirect to the sign-in
page (``/signin?error=failed`` or ``/signin?error=denied``)."""


class SignInFailed(Exception):
    """The sign-in cannot go on: cancelled, refused or broken at the provider, a state that
    does not match, a provider that is not configured. ``reason`` is for the log and never
    holds a secret or personal data."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SignInDenied(Exception):
    """The provider vouched for the account, but its email is not on the beta list. The
    account waits in Redis under ``denial_id`` for the sign-in page to name it."""

    def __init__(self, denial_id: str) -> None:
        super().__init__("account not on the beta list")
        self.denial_id = denial_id
