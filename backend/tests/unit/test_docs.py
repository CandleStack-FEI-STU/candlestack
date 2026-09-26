import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from candlestack.core import Problem, problem_responses


def test_scalar_docs_page(client: TestClient) -> None:
    response = client.get("/api/v1/docs")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>CandleStack API</title>" in response.text
    assert "/api/v1/openapi.json" in response.text


def test_scalar_docs_page_is_branded_and_trimmed(client: TestClient) -> None:
    page = client.get("/api/v1/docs").text

    assert 'href="/favicon.svg"' in page
    assert "fastapi.tiangolo.com" not in page
    assert '"documentDownloadType": "none"' in page
    assert '"showDeveloperTools": "never"' in page
    assert '"mcp": {"disabled": true}' in page
    assert "https://www.scalar.com" in page  # the CSS that hides Scalar's footer link


def test_openapi_schema(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "CandleStack API"
    assert schema["info"]["version"] == "1.2.3"
    assert "/api/health" in schema["paths"]


def test_openapi_server_is_the_current_host(client: TestClient) -> None:
    schema = client.get("/api/v1/openapi.json").json()

    # Relative, so Scalar's code examples use the host the docs are opened on.
    assert schema["servers"] == [{"url": "/", "description": "This environment"}]


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/api/docs"])
def test_no_other_docs(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_errors_are_documented_as_problem_details(app: FastAPI) -> None:
    @app.get("/api/test/things/{thing_id}", responses=problem_responses(404))
    async def thing(thing_id: int) -> dict[str, int]:
        return {"id": thing_id}

    schema = app.openapi()

    responses = schema["paths"]["/api/test/things/{thing_id}"]["get"]["responses"]
    problem = {"application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}}
    assert responses["404"]["content"] == problem
    assert responses["422"]["content"] == problem
    assert responses["422"]["description"] == "Invalid request"
    assert "Problem" in schema["components"]["schemas"]
    assert "HTTPValidationError" not in schema["components"]["schemas"]


def test_an_explicit_422_description_is_kept(app: FastAPI) -> None:
    @app.get("/api/test/items", responses=problem_responses(422))
    async def items(limit: int = 1) -> dict[str, int]:
        return {"limit": limit}

    @app.get(
        "/api/test/limited",
        responses={422: {"model": Problem, "description": "Period out of range"}},
    )
    async def limited(limit: int = 1) -> dict[str, int]:
        return {"limit": limit}

    paths = app.openapi()["paths"]

    assert paths["/api/test/items"]["get"]["responses"]["422"]["description"] == (
        "Unprocessable Content"
    )
    assert paths["/api/test/limited"]["get"]["responses"]["422"]["description"] == (
        "Period out of range"
    )
