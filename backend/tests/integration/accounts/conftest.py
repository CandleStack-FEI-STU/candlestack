"""Fixtures of the accounts integration tests: the app on a real Postgres (emptied before each
test) and a real Redis (flushed before each test), with GitHub and Google mocked by respx.

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
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from candlestack.accounts.oauth import GITHUB_API_URL, GOOGLE_USERINFO_URL
from candlestack.core import Settings, create_redis
from candlestack.main import create_app

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
ORIGIN = {"Origin": "http://testserver"}


async def _run_sql(url: str, statement: str) -> list[Any]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            result = await connection.execute(text(statement))
            return list(result.all()) if result.returns_rows else []
    finally:
        await engine.dispose()


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
def sql(database_url: str) -> Callable[[str], list[Any]]:
    """Runs one statement in the test database: ``sql("SELECT id FROM users")``, the rows."""
    return lambda statement: asyncio.run(_run_sql(database_url, statement))


@pytest.fixture
def forget_pending(redis_url: str) -> Callable[[], None]:
    """Empties Redis, as if every pending sign-in and denial had expired."""
    return lambda: asyncio.run(_flush(redis_url))


@pytest.fixture
def auth_keys(redis_url: str) -> Callable[[], list[str]]:
    """The keys of pending sign-ins and denials in Redis, sorted."""
    return lambda: asyncio.run(_auth_keys(redis_url))


@pytest.fixture(autouse=True)
def empty_stores(sql: Callable[[str], list[Any]], forget_pending: Callable[[], None]) -> None:
    sql("TRUNCATE users, identities, sessions, user_preferences")
    forget_pending()


@pytest.fixture
def settings(database_url: str, redis_url: str) -> Settings:
    return Settings(
        app_env="test",
        database_url=database_url,
        redis_url=redis_url,
        oauth_github_client_id="gh-client",
        oauth_github_client_secret="gh-secret",
        oauth_google_client_id="google-client",
        oauth_google_client_secret="google-secret",
        beta_allowlist=frozenset({"ada@example.com"}),
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


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
        params = {"next": next_path} if next_path is not None else {}
        if intent is not None:
            params["intent"] = intent
        response = self.get(f"/api/v1/auth/{provider}/start", params=params)
        if response.status_code == 302 and response.headers["location"].startswith("https://"):
            query = parse_qs(urlsplit(response.headers["location"]).query)
            self.providers.challenge = query["code_challenge"][0]
        return response

    def callback(self, provider: str, **params: str) -> httpx2.Response:
        return self.get(f"/api/v1/auth/{provider}/callback", params=params)

    def sign_in(self, provider: str = "github", next_path: str | None = None) -> httpx2.Response:
        """Starts a sign-in, consents at the provider and returns the callback's response."""
        start = self.start(provider, next_path)
        state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
        return self.callback(provider, code="the-code", state=state)

    def connect(self, provider: str, next_path: str | None = None) -> httpx2.Response:
        """Starts connecting a sign-in method, consents at the provider and returns the
        callback's response."""
        start = self.start(provider, next_path, intent="connect")
        state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
        return self.callback(provider, code="the-code", state=state)

    def sign_out(self) -> httpx2.Response:
        return self.post("/api/v1/auth/sign-out", headers=ORIGIN)

    def me(self) -> httpx2.Response:
        return self.get("/api/v1/me")


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


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
