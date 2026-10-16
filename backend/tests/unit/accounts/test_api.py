"""The accounts routes up to where they would need Postgres or Redis; the flows with both are
integration tests (tests/integration/accounts)."""

import logging
from dataclasses import dataclass, field

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.routing import NoMatchFound

from candlestack.accounts import dev_sign_in_allowed
from candlestack.core import Settings
from candlestack.core.ratelimit import get_rate_limiter
from candlestack.main import create_app

PROBLEMS = "https://candlestack.tech/problems/"
ORIGIN = {"Origin": "http://testserver"}


@dataclass
class FakeLimiter:
    wait: float = 0.0
    keys: list[str] = field(default_factory=list)

    async def hit(self, key: str, limit: int, cost: int = 1, window: int = 60) -> float:
        self.keys.append(key)
        return self.wait


@pytest.fixture
def limiter() -> FakeLimiter:
    return FakeLimiter()


@pytest.fixture
def app(app: FastAPI, limiter: FakeLimiter) -> FastAPI:
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    return app


@pytest.mark.parametrize(
    ("app_env", "allowed"),
    [("local", True), ("test", True), ("stage", False), ("prod", False)],
)
def test_dev_sign_in_only_where_allowed(app_env: str, allowed: bool) -> None:
    app = create_app(Settings(app_env=app_env))

    assert dev_sign_in_allowed(app_env) is allowed
    try:
        app.url_path_for("dev_sign_in")
    except NoMatchFound:
        registered = False
    else:
        registered = True
    assert registered is allowed


def test_dev_sign_in_is_not_in_the_api_reference(client: TestClient) -> None:
    paths = client.get("/api/v1/openapi.json").json()["paths"]

    assert "/api/v1/auth/dev" not in paths
    assert "/api/v1/auth/{provider}/callback" not in paths


def test_me_without_a_session(client: TestClient) -> None:
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["type"] == PROBLEMS + "not-signed-in"


def test_denied_without_a_denial(client: TestClient) -> None:
    response = client.get("/api/v1/auth/denied")

    assert response.status_code == 404
    assert response.json()["type"] == PROBLEMS + "not-found"


def test_sign_out_without_a_session(client: TestClient) -> None:
    response = client.post("/api/v1/auth/sign-out", headers=ORIGIN)

    assert response.status_code == 204
    assert response.headers["set-cookie"].startswith('session=""; ')


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "https://evil.example"},
        {"Origin": "http://testserver.evil.example"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "same-site"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_sign_out_from_another_origin(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post("/api/v1/auth/sign-out", headers=headers)

    assert response.status_code == 403
    assert response.json()["type"] == PROBLEMS + "cross-origin-request"
    assert "set-cookie" not in response.headers


def test_sign_out_same_origin_by_fetch_metadata(client: TestClient) -> None:
    response = client.post("/api/v1/auth/sign-out", headers={"Sec-Fetch-Site": "same-origin"})

    assert response.status_code == 204


def test_start_with_a_provider_that_is_not_configured(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        response = client.get("/api/v1/auth/google/start", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/signin?error=failed"
    assert "set-cookie" not in response.headers
    assert "Sign-in with google failed: google sign-in is not configured" in caplog.text


def test_start_with_an_unknown_provider(client: TestClient) -> None:
    response = client.get("/api/v1/auth/facebook/start", follow_redirects=False)

    assert response.status_code == 422


def test_sign_in_rate_limit(client: TestClient, limiter: FakeLimiter) -> None:
    limiter.wait = 12.3

    response = client.get("/api/v1/auth/github/start", follow_redirects=False)

    assert response.status_code == 429
    assert response.headers["retry-after"] == "13"
    assert response.json()["type"] == PROBLEMS + "rate-limited"
    assert limiter.keys == ["accounts:rl:testclient"]


def test_callback_over_the_rate_limit_fails(client: TestClient, limiter: FakeLimiter) -> None:
    limiter.wait = 5

    response = client.get("/api/v1/auth/github/callback?code=c&state=s", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/signin?error=failed"
