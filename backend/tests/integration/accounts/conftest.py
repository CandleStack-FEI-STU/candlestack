"""Fixtures of the accounts integration tests: the app on a real Postgres, emptied before each
test (tests/integration/conftest.py), and a real Redis (flushed before each test), with GitHub
and Google mocked by respx.

Test modules cannot import this file, so the helpers they need hang on the ``providers``
fixture (``Providers``) and on ``Browser``, a TestClient that signs in like a browser.
"""

import asyncio
from collections.abc import Callable, Iterator
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

import httpx
import httpx2
import pytest
import respx
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from fastapi.testclient import TestClient
from pydantic import SecretStr

from candlestack.accounts.oauth import GITHUB_API_URL, GOOGLE_USERINFO_URL
from candlestack.core import Settings, create_redis
from candlestack.main import create_app

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
ORIGIN = {"Origin": "http://testserver"}
# What a browser sends with a navigation from a page of the app, e.g. the Connect link.
LINK = {"Sec-Fetch-Site": "same-origin"}


async def _flush(url: str) -> None:
    redis = create_redis(url)
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()


async def _auth_keys(url: str) -> list[str]:
    redis = create_redis(url)
    try:
        keys = cast("list[bytes]", await redis.keys("auth:*"))  # responses stay bytes
        return sorted(key.decode() for key in keys)
    finally:
        await redis.aclose()


@pytest.fixture
def forget_pending(redis_url: str) -> Callable[[], None]:
    """Empties Redis, as if every pending sign-in and denial had expired."""
    return lambda: asyncio.run(_flush(redis_url))


@pytest.fixture
def auth_keys(redis_url: str) -> Callable[[], list[str]]:
    """The keys of pending sign-ins and denials in Redis, sorted."""
    return lambda: asyncio.run(_auth_keys(redis_url))


@pytest.fixture(autouse=True)
def empty_stores(empty_tables: None, forget_pending: Callable[[], None]) -> None:
    forget_pending()


@pytest.fixture
def settings(settings: Settings) -> Settings:
    """The shared settings with GitHub and Google configured and Ada on the beta list."""
    return settings.model_copy(
        update={
            "oauth_github_client_id": "gh-client",
            "oauth_github_client_secret": SecretStr("gh-secret"),
            "oauth_google_client_id": "google-client",
            "oauth_google_client_secret": SecretStr("google-secret"),
            "beta_allowlist": frozenset({"ada@example.com"}),
        }
    )


class Providers:
    """GitHub and Google as respx routes. Each token request checks the PKCE verifier against
    the challenge of the last authorization URL the test followed."""

    def __init__(self, router: respx.MockRouter) -> None:
        self.router = router
        self.challenge: str | None = None
        self.github_account()
        self.google_account()

    def _token(self, access_token: str) -> Any:
        def answer(request: httpx.Request) -> httpx.Response:
            body = parse_qs(request.content.decode())
            if create_s256_code_challenge(body["code_verifier"][0]) != self.challenge:
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": access_token, "token_type": "bearer"})

        return answer

    def github_account(
        self,
        *,
        subject: int = 42,
        login: str = "ada",
        name: str | None = "Ada Lovelace",
        email: str = "Ada@Example.com",
        verified: bool = True,
    ) -> None:
        self.router.post(GITHUB_TOKEN_URL).mock(side_effect=self._token("gh-token"))
        self.router.get(f"{GITHUB_API_URL}/user").respond(
            200, json={"id": subject, "login": login, "name": name}
        )
        self.router.get(f"{GITHUB_API_URL}/user/emails").respond(
            200, json=[{"email": email, "primary": True, "verified": verified}]
        )

    def google_account(
        self, *, subject: str = "1077", email: str = "ada@example.com", name: str = "Ada L."
    ) -> None:
        self.router.post(GOOGLE_TOKEN_URL).mock(side_effect=self._token("g-token"))
        self.router.get(GOOGLE_USERINFO_URL).respond(
            200, json={"sub": subject, "email": email, "email_verified": True, "name": name}
        )


@pytest.fixture
def providers() -> Iterator[Providers]:
    with respx.mock(assert_all_called=False) as router:
        yield Providers(router)


class Browser:
    """A browser on the app: its own cookies, kept as a browser keeps them, and redirects not
    followed. Several browsers share the one TestClient (and so the app's event loop)."""

    def __init__(self, client: TestClient, providers: Providers) -> None:
        self._client = client
        self._cookies = httpx2.Cookies()
        self.providers = providers

    def request(self, method: str, url: str, **kwargs: Any) -> httpx2.Response:
        self._client.cookies = self._cookies
        try:
            return self._client.request(method, url, follow_redirects=False, **kwargs)
        finally:
            self._cookies = self._client.cookies

    def get(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("POST", url, **kwargs)

    def cookie(self, name: str) -> str | None:
        return self._cookies.get(name)

    def set_cookie(self, name: str, value: str) -> None:
        self._cookies.set(name, value, domain="testserver.local")

    def patch(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("PATCH", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("DELETE", url, **kwargs)

    def start(
        self, provider: str, next_path: str | None = None, intent: str | None = None
    ) -> httpx2.Response:
        """Opens the start of a sign-in, or with `intent` ``connect`` follows the Connect link
        of Settings."""
        params = {"next": next_path} if next_path is not None else {}
        if intent is not None:
            params["intent"] = intent
        headers = LINK if intent == "connect" else {}
        response = self.get(f"/api/v1/auth/{provider}/start", params=params, headers=headers)
        if response.status_code == 302 and response.headers["location"].startswith("https://"):
            query = parse_qs(urlsplit(response.headers["location"]).query)
            self.providers.challenge = query["code_challenge"][0]
        return response

    @staticmethod
    def state_of(start: httpx2.Response) -> str:
        """The state a start sends to the provider."""
        return parse_qs(urlsplit(start.headers["location"]).query)["state"][0]

    def callback(self, provider: str, **params: str) -> httpx2.Response:
        return self.get(f"/api/v1/auth/{provider}/callback", params=params)

    def _round_trip(
        self, provider: str, next_path: str | None, intent: str | None
    ) -> httpx2.Response:
        """Starts, consents at the provider and returns the callback's response."""
        start = self.start(provider, next_path, intent)
        return self.callback(provider, code="the-code", state=self.state_of(start))

    def sign_in(self, provider: str = "github", next_path: str | None = None) -> httpx2.Response:
        """Signs in; the callback's response."""
        return self._round_trip(provider, next_path, None)

    def connect(self, provider: str, next_path: str | None = None) -> httpx2.Response:
        """Connects a sign-in method in Settings; the callback's response."""
        return self._round_trip(provider, next_path, "connect")

    def sign_out(self) -> httpx2.Response:
        return self.post("/api/v1/auth/sign-out", headers=ORIGIN)

    def me(self) -> httpx2.Response:
        return self.get("/api/v1/me")


@pytest.fixture
def browser(client: TestClient, providers: Providers) -> Browser:
    return Browser(client, providers)


@pytest.fixture
def browser_without_postgres(settings: Settings, providers: Providers) -> Iterator[Browser]:
    """A browser on an app whose Postgres is unreachable: nothing listens on port 1."""
    unreachable = settings.model_copy(
        update={
            "database_url": SecretStr("postgresql+asyncpg://nobody:nothing@127.0.0.1:1/nothing")
        }
    )
    with TestClient(create_app(unreachable)) as client:
        yield Browser(client, providers)


@pytest.fixture
def other_browser(client: TestClient, providers: Providers) -> Browser:
    return Browser(client, providers)


@pytest.fixture
def third_browser(client: TestClient, providers: Providers) -> Browser:
    return Browser(client, providers)
