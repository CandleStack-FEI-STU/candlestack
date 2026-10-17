"""The Backtests page and the Dashboard over HTTP with the built image and its migrated table;
the dev user has no backtests."""

import httpx
import pytest

pytestmark = pytest.mark.e2e

ORIGIN = {"Origin": "http://testserver"}
NO_BACKTESTS = {"all": 0, "starred": 0, "failed": 0}


def test_the_backtests_list(http: httpx.Client) -> None:
    http.post("/api/v1/auth/dev", headers=ORIGIN)

    response = http.get("/api/v1/backtests", params={"q": "aapl", "sort": "sharpe", "page": 2})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "backtests": [],
        "total": 0,
        "page": 2,
        "pages": 1,
        "counts": NO_BACKTESTS,
        "models": [],
    }


def test_the_dashboard(http: httpx.Client) -> None:
    http.post("/api/v1/auth/dev", headers=ORIGIN)

    response = http.get("/api/v1/dashboard")

    assert response.status_code == 200
    assert response.json()["counts"] == NO_BACKTESTS
    assert response.json()["last"] == []


def test_starring_an_unknown_backtest(http: httpx.Client) -> None:
    http.post("/api/v1/auth/dev", headers=ORIGIN)

    response = http.patch("/api/v1/backtests/bt_zzzzzzzzzz", json={"starred": True}, headers=ORIGIN)

    assert response.status_code == 404
    assert response.json()["type"] == "https://candlestack.tech/problems/not-found"
