from collections.abc import AsyncIterator, Iterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from authlib.oauth2.rfc7636 import create_s256_code_challenge

from candlestack.accounts.errors import SignInFailed
from candlestack.accounts.oauth import GITHUB_API_URL, GOOGLE_USERINFO_URL, OAuthClient
from candlestack.accounts.schemas import Provider
from candlestack.core import Settings

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
VERIFIER = "v" * 64

pytestmark = pytest.mark.anyio


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="stage",
        oauth_github_client_id="gh-client",
        oauth_github_client_secret="gh-secret",
        oauth_google_client_id="google-client",
        oauth_google_client_secret="google-secret",
    )


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def oauth(settings: Settings, http: httpx.AsyncClient) -> OAuthClient:
    return OAuthClient(settings, http)


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as router:
        yield router


def github(
    mock: respx.MockRouter,
    *,
    user: dict[str, Any] | None = None,
    emails: list[dict[str, Any]] | None = None,
) -> respx.Route:
    token = mock.post(GITHUB_TOKEN_URL).respond(
        200, json={"access_token": "gh-token", "token_type": "bearer", "scope": "read:user"}
    )
    mock.get(f"{GITHUB_API_URL}/user").respond(
        200, json=user or {"id": 42, "login": "ada", "name": "Ada Lovelace"}
    )
    mock.get(f"{GITHUB_API_URL}/user/emails").respond(
        200,
        json=emails
        if emails is not None
        else [
            {"email": "old@example.com", "primary": False, "verified": True},
            {"email": "Ada@Example.com", "primary": True, "verified": True},
        ],
    )
    return token


async def test_github_authorization_url(oauth: OAuthClient) -> None:
    url = oauth.authorization_url(Provider.github, state="the-state", verifier=VERIFIER)

    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == (
        "https://github.com/login/oauth/authorize"
    )
    assert parse_qs(parts.query) == {
        "response_type": ["code"],
        "client_id": ["gh-client"],
        "redirect_uri": ["https://stage.candlestack.tech/api/v1/auth/github/callback"],
        "scope": ["read:user user:email"],
        "state": ["the-state"],
        "code_challenge": [create_s256_code_challenge(VERIFIER)],
        "code_challenge_method": ["S256"],
    }


async def test_google_authorization_url(oauth: OAuthClient) -> None:
    url = oauth.authorization_url(Provider.google, state="the-state", verifier=VERIFIER)

    parts = urlsplit(url)
    query = parse_qs(parts.query)
    assert parts.netloc == "accounts.google.com"
    assert query["client_id"] == ["google-client"]
    assert query["scope"] == ["openid email profile"]
    assert query["redirect_uri"] == ["https://stage.candlestack.tech/api/v1/auth/google/callback"]


@pytest.mark.parametrize("provider", list(Provider))
async def test_a_provider_without_keys_is_not_configured(
    provider: Provider, http: httpx.AsyncClient
) -> None:
    oauth = OAuthClient(Settings(app_env="stage", oauth_github_client_id="only-the-id"), http)

    with pytest.raises(SignInFailed, match="not configured"):
        oauth.authorization_url(provider, state="s", verifier=VERIFIER)


async def test_github_account_with_its_primary_verified_email(
    oauth: OAuthClient, mock: respx.MockRouter
) -> None:
    token = github(mock)

    account = await oauth.fetch_account(Provider.github, code="the-code", verifier=VERIFIER)

    assert account.provider is Provider.github
    assert account.subject == "42"
    assert account.email == "ada@example.com"
    assert account.name == "Ada Lovelace"
    assert account.login == "ada"
    # Sentry keeps the reprs of a failed frame's variables: no personal data in them.
    assert repr(account) == "ProviderAccount(provider=<Provider.github: 'github'>, subject='42')"
    body = parse_qs(token.calls.last.request.content.decode())
    assert body == {
        "grant_type": ["authorization_code"],
        "code": ["the-code"],
        "redirect_uri": ["https://stage.candlestack.tech/api/v1/auth/github/callback"],
        "code_verifier": [VERIFIER],
        "client_id": ["gh-client"],
        "client_secret": ["gh-secret"],
    }
    assert token.calls.last.request.headers["accept"] == "application/json"
    user_request = mock.calls[1].request
    assert user_request.headers["authorization"] == "Bearer gh-token"
    assert user_request.headers["x-github-api-version"] == "2022-11-28"


@pytest.mark.parametrize(
    "emails",
    [
        [],
        [{"email": "ada@example.com", "primary": True, "verified": False}],
        [{"email": "ada@example.com", "primary": False, "verified": True}],
    ],
)
async def test_github_account_without_a_verified_primary_email(
    oauth: OAuthClient, mock: respx.MockRouter, emails: list[dict[str, Any]]
) -> None:
    github(mock, emails=emails)

    with pytest.raises(SignInFailed, match="no verified primary email"):
        await oauth.fetch_account(Provider.github, code="the-code", verifier=VERIFIER)


async def test_google_account(oauth: OAuthClient, mock: respx.MockRouter) -> None:
    mock.post(GOOGLE_TOKEN_URL).respond(200, json={"access_token": "g-token", "id_token": "x"})
    userinfo = mock.get(GOOGLE_USERINFO_URL).respond(
        200,
        json={"sub": "1077", "email": "Ada@Gmail.com", "email_verified": True, "name": "Ada"},
    )

    account = await oauth.fetch_account(Provider.google, code="the-code", verifier=VERIFIER)

    assert (account.subject, account.email, account.name, account.login) == (
        "1077",
        "ada@gmail.com",
        "Ada",
        None,
    )
    assert userinfo.calls.last.request.headers["authorization"] == "Bearer g-token"


@pytest.mark.parametrize(
    "userinfo",
    [{"sub": "1077", "email": "ada@gmail.com", "email_verified": False}, {"sub": "1077"}],
)
async def test_google_account_without_a_verified_email(
    oauth: OAuthClient, mock: respx.MockRouter, userinfo: dict[str, Any]
) -> None:
    mock.post(GOOGLE_TOKEN_URL).respond(200, json={"access_token": "g-token"})
    mock.get(GOOGLE_USERINFO_URL).respond(200, json=userinfo)

    with pytest.raises(SignInFailed, match="no verified email"):
        await oauth.fetch_account(Provider.google, code="the-code", verifier=VERIFIER)


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx.Response(200, json={"error": "bad_verification_code"}), "bad_verification_code"),
        (httpx.Response(400, json={"error": "invalid_grant"}), "invalid_grant"),
        (httpx.Response(200, json={}), "no token"),
        (httpx.Response(502, text="Bad gateway"), "HTTP 502"),
        (httpx.Response(200, text="<html>"), "unexpected response"),
    ],
)
async def test_a_refused_code(
    oauth: OAuthClient, mock: respx.MockRouter, response: httpx.Response, reason: str
) -> None:
    mock.post(GITHUB_TOKEN_URL).mock(return_value=response)

    with pytest.raises(SignInFailed, match=reason):
        await oauth.fetch_account(Provider.github, code="the-code", verifier=VERIFIER)


async def test_a_failing_profile_request(oauth: OAuthClient, mock: respx.MockRouter) -> None:
    mock.post(GOOGLE_TOKEN_URL).respond(200, json={"access_token": "g-token"})
    mock.get(GOOGLE_USERINFO_URL).respond(401)

    with pytest.raises(SignInFailed, match="HTTP 401"):
        await oauth.fetch_account(Provider.google, code="the-code", verifier=VERIFIER)


async def test_an_unreachable_provider(oauth: OAuthClient, mock: respx.MockRouter) -> None:
    mock.post(GITHUB_TOKEN_URL).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(SignInFailed, match="github is unreachable"):
        await oauth.fetch_account(Provider.github, code="the-code", verifier=VERIFIER)
