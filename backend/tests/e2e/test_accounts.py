"""Signing in over HTTP with the built image and its migrated Postgres. The stack runs as
``APP_ENV=test``, so the dev sign-in stands in for GitHub and Google."""

import httpx
import pytest

pytestmark = pytest.mark.e2e

ORIGIN = {"Origin": "http://testserver"}


def test_dev_sign_in_me_and_sign_out(http: httpx.Client) -> None:
    assert http.get("/api/v1/me").status_code == 401

    signed_in = http.post("/api/v1/auth/dev", headers=ORIGIN)

    assert signed_in.status_code == 204
    me = http.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["email"] == "dev@candlestack.tech"

    signed_out = http.post("/api/v1/auth/sign-out", headers=ORIGIN)

    assert signed_out.status_code == 204
    assert http.get("/api/v1/me").status_code == 401


def test_sign_in_without_oauth_keys_fails_gracefully(http: httpx.Client) -> None:
    response = http.get("/api/v1/auth/github/start", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/signin?error=failed"
