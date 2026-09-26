import logging

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from candlestack.core import ProblemError

PROBLEM = "application/problem+json"


@pytest.fixture
def app(app: FastAPI) -> FastAPI:
    @app.get("/api/test/limited")
    async def limited() -> None:
        raise ProblemError(
            429,
            "rate-limited",
            "Too many requests",
            "More than 60 requests in a minute. Try again in 12 s.",
            headers={"Retry-After": "12"},
            extensions={"limit": 60},
        )

    @app.get("/api/test/items")
    async def items(limit: int = Query(le=100)) -> dict[str, int]:
        return {"limit": limit}

    @app.get("/api/test/crash")
    async def crash() -> None:
        raise RuntimeError("database password is hunter2")

    return app


def test_problem_error(client: TestClient) -> None:
    response = client.get("/api/test/limited")

    assert response.status_code == 429
    assert response.headers["content-type"] == PROBLEM
    assert response.headers["retry-after"] == "12"
    assert response.json() == {
        "type": "https://candlestack.tech/problems/rate-limited",
        "title": "Too many requests",
        "status": 429,
        "detail": "More than 60 requests in a minute. Try again in 12 s.",
        "limit": 60,
    }


def test_problem_extensions_cannot_redefine_members() -> None:
    with pytest.raises(ValueError, match="status"):
        ProblemError(400, "bad", "Bad", "Bad.", extensions={"status": 200})


@pytest.mark.parametrize(
    ("query", "detail"),
    [
        ("limit=abc", "query parameter 'limit': Input should be a valid integer"),
        ("limit=101", "query parameter 'limit': Input should be less than or equal to 100"),
        ("", "query parameter 'limit': Field required"),
    ],
)
def test_validation_error(client: TestClient, query: str, detail: str) -> None:
    response = client.get(f"/api/test/items?{query}")

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM
    body = response.json()
    assert body["type"] == "https://candlestack.tech/problems/validation"
    assert body["title"] == "Invalid request"
    assert body["status"] == 422
    assert body["detail"].startswith(detail)
    assert body["errors"][0]["loc"] == ["query", "limit"]


def test_unhandled_error_is_a_500_without_internals(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        response = client.get("/api/test/crash")

    assert response.status_code == 500
    assert response.headers["content-type"] == PROBLEM
    body = response.json()
    assert body["type"] == "https://candlestack.tech/problems/internal-error"
    assert body["status"] == 500
    assert "hunter2" not in response.text
    assert "RuntimeError" not in response.text
    # The cause goes to the log instead, with the id the client got.
    [record] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert record.exc_info is not None
    assert "hunter2" in str(record.exc_info[1])
    assert response.headers["x-request-id"]


def test_unknown_path_is_a_404_problem(client: TestClient) -> None:
    response = client.get("/api/nothing-here")

    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM
    assert response.json() == {
        "type": "https://candlestack.tech/problems/not-found",
        "title": "Not Found",
        "status": 404,
        "detail": "Nothing at /api/nothing-here. The API reference is at /api/v1/docs.",
    }


def test_wrong_method_is_a_405_problem(client: TestClient) -> None:
    response = client.post("/api/health")

    assert response.status_code == 405
    assert response.headers["content-type"] == PROBLEM
    assert response.headers["allow"] == "GET"
    assert response.json()["detail"] == "POST is not allowed on /api/health; use GET."
