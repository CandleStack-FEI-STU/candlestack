import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from candlestack.core import problem_responses


def test_scalar_docs_page(client: TestClient) -> None:
    response = client.get("/api/v1/docs")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>CandleStack API</title>" in response.text
    assert "/api/v1/openapi.json" in response.text


def test_openapi_schema(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "CandleStack API"
    assert schema["info"]["version"] == "1.2.3"
    assert "/api/health" in schema["paths"]


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
    assert "Problem" in schema["components"]["schemas"]
    assert "HTTPValidationError" not in schema["components"]["schemas"]
