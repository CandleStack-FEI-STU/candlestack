import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.asyncio import Redis


def test_lifespan_opens_and_closes_the_shared_clients(app: FastAPI) -> None:
    with TestClient(app):
        assert isinstance(app.state.redis, Redis)
        assert isinstance(app.state.http, httpx.AsyncClient)
        assert app.state.http.headers["User-Agent"] == "candlestack/1.2.3"

    assert app.state.http.is_closed


def test_module_level_app_for_granian() -> None:
    from candlestack.main import app

    assert isinstance(app, FastAPI)
    assert app.openapi_url == "/api/v1/openapi.json"
