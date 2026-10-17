"""GitHub and Google sign-in: the OAuth 2.0 authorization code flow with PKCE (S256).

Authlib builds the protocol messages (the authorization URL, the code challenge, the token
request). The requests go through the app's shared HTTP client: Authlib's own async client
runs on httpx2, which the tests could not mock and which the app does not otherwise use.
"""

from dataclasses import dataclass, field

import httpx
from authlib.oauth2.client import DEFAULT_HEADERS
from authlib.oauth2.rfc6749.parameters import prepare_grant_uri, prepare_token_request
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from pydantic import BaseModel, TypeAdapter, ValidationError

from candlestack.accounts.errors import SignInFailed
from candlestack.accounts.schemas import Provider
from candlestack.core import Settings, request_with_retry

GITHUB_API_URL = "https://api.github.com"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_GITHUB_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


@dataclass(frozen=True, slots=True)
class _Endpoints:
    authorize_url: str
    exchange_url: str
    scope: str


_ENDPOINTS = {
    Provider.github: _Endpoints(
        authorize_url="https://github.com/login/oauth/authorize",
        exchange_url="https://github.com/login/oauth/access_token",
        scope="read:user user:email",
    ),
    Provider.google: _Endpoints(
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        exchange_url="https://oauth2.googleapis.com/token",
        scope="openid email profile",
    ),
}


@dataclass(frozen=True, slots=True)
class ProviderAccount:
    """The account the provider signed in, with its verified email (lowercased). Its repr
    leaves out the personal data: Sentry keeps the reprs of the variables of a failed frame."""

    provider: Provider
    subject: str
    email: str = field(repr=False)
    name: str | None = field(repr=False)
    login: str | None = field(repr=False)


class _Token(BaseModel):
    access_token: str | None = None
    error: str | None = None


class _GitHubUser(BaseModel):
    id: int
    login: str
    name: str | None = None


class _GitHubEmail(BaseModel):
    email: str
    primary: bool
    verified: bool


_GITHUB_EMAILS = TypeAdapter(list[_GitHubEmail])


class _GoogleUser(BaseModel):
    sub: str
    email: str | None = None
    email_verified: bool = False
    name: str | None = None


class OAuthClient:
    """Talks to GitHub and Google for one sign-in at a time."""

    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http

    def _credentials(self, provider: Provider) -> tuple[str, str]:
        """The app's client ID and secret at the provider; a provider without both is not
        configured, and nobody signs in with it."""
        settings = self._settings
        if provider is Provider.github:
            client_id = settings.oauth_github_client_id
            secret = settings.oauth_github_client_secret.get_secret_value()
        else:
            client_id = settings.oauth_google_client_id
            secret = settings.oauth_google_client_secret.get_secret_value()
        if not client_id or not secret:
            raise SignInFailed(f"{provider} sign-in is not configured")
        return client_id, secret

    def _redirect_uri(self, provider: Provider) -> str:
        return f"{self._settings.public_url}/api/v1/auth/{provider}/callback"

    def authorization_url(self, provider: Provider, *, state: str, verifier: str) -> str:
        """The provider's consent page, which returns to the callback with a code and `state`.

        Raises:
            SignInFailed: The provider is not configured.
        """
        client_id, _ = self._credentials(provider)
        endpoints = _ENDPOINTS[provider]
        return prepare_grant_uri(
            endpoints.authorize_url,
            client_id=client_id,
            response_type="code",
            redirect_uri=self._redirect_uri(provider),
            scope=endpoints.scope,
            state=state,
            code_challenge=create_s256_code_challenge(verifier),
            code_challenge_method="S256",
        )

    async def fetch_account(
        self, provider: Provider, *, code: str, verifier: str
    ) -> ProviderAccount:
        """Trades the callback's code for an access token and reads the account with it.

        Raises:
            SignInFailed: The provider refused the code, failed, or has no verified email for
                the account.
        """
        try:
            token = await self._access_token(provider, code=code, verifier=verifier)
            if provider is Provider.github:
                return await self._github_account(token)
            return await self._google_account(token)
        except httpx.HTTPError as error:
            raise SignInFailed(f"{provider} is unreachable ({type(error).__name__})") from error
        except ValidationError as error:
            raise SignInFailed(f"{provider} sent an unexpected response") from error

    async def _access_token(self, provider: Provider, *, code: str, verifier: str) -> str:
        client_id, secret = self._credentials(provider)
        body = prepare_token_request(
            "authorization_code",
            code=code,
            redirect_uri=self._redirect_uri(provider),
            code_verifier=verifier,
            client_id=client_id,
            client_secret=secret,
        )
        # Not retried: a code works once.
        response = await self._http.post(
            _ENDPOINTS[provider].exchange_url, content=body, headers=DEFAULT_HEADERS
        )
        if response.status_code >= 500:
            raise SignInFailed(f"{provider} token endpoint answered HTTP {response.status_code}")
        token = _Token.model_validate_json(response.content)
        if token.access_token is None:
            raise SignInFailed(f"{provider} refused the code ({token.error or 'no token'})")
        return token.access_token

    async def _get(self, url: str, token: str, headers: dict[str, str] | None = None) -> bytes:
        response = await request_with_retry(
            self._http,
            "GET",
            url,
            headers={**(headers or {}), "Authorization": f"Bearer {token}"},
        )
        if response.status_code != 200:
            raise SignInFailed(f"GET {url} answered HTTP {response.status_code}")
        return response.content

    async def _github_account(self, token: str) -> ProviderAccount:
        user = _GitHubUser.model_validate_json(
            await self._get(f"{GITHUB_API_URL}/user", token, _GITHUB_HEADERS)
        )
        emails = _GITHUB_EMAILS.validate_json(
            await self._get(f"{GITHUB_API_URL}/user/emails", token, _GITHUB_HEADERS)
        )
        email = next((e.email for e in emails if e.primary and e.verified), None)
        if email is None:
            raise SignInFailed("the GitHub account has no verified primary email")
        return ProviderAccount(
            provider=Provider.github,
            subject=str(user.id),
            email=email.lower(),
            name=user.name or None,
            login=user.login,
        )

    async def _google_account(self, token: str) -> ProviderAccount:
        user = _GoogleUser.model_validate_json(await self._get(GOOGLE_USERINFO_URL, token))
        if user.email is None or not user.email_verified:
            raise SignInFailed("the Google account has no verified email")
        return ProviderAccount(
            provider=Provider.google,
            subject=user.sub,
            email=user.email.lower(),
            name=user.name or None,
            login=None,
        )
