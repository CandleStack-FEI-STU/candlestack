"""The CandleStack API app, served by granian: ``candlestack.main:app``."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from scalar_fastapi import AgentScalarConfig, get_scalar_api_reference

from candlestack.core import (
    RequestContextMiddleware,
    Settings,
    create_http_client,
    create_redis,
    document_problems,
    get_settings,
    health_router,
    install_error_handlers,
    setup_logging,
)
from candlestack.data import build_data_service, data_router

TITLE = "CandleStack API"
DESCRIPTION = (
    "HTTP API of CandleStack, a lab for experiments on financial time series. "
    "Market data covers crypto from Binance and US stocks from Alpaca. "
    "Times in responses are UTC epoch seconds; requests also accept ISO 8601. "
    "Errors are RFC 9457 problem details (`application/problem+json`)."
)
OPENAPI_URL = "/api/v1/openapi.json"
DOCS_URL = "/api/v1/docs"


class CandleStackAPI(FastAPI):
    def openapi(self) -> dict[str, Any]:
        if self.openapi_schema is None:
            self.openapi_schema = document_problems(super().openapi())
        return self.openapi_schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Opens the shared clients on ``app.state`` (``redis``, ``http``) and builds the market
    data service on them (``data_service``)."""
    settings: Settings = app.state.settings
    app.state.redis = create_redis(settings.redis_url)
    try:
        async with create_http_client(settings) as http:
            app.state.http = http
            app.state.data_service = build_data_service(settings, app.state.redis, http)
            yield
    finally:
        await app.state.redis.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Builds the app; `settings` default to the environment (``get_settings()``)."""
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    app = CandleStackAPI(
        title=TITLE,
        version=settings.app_version,
        description=DESCRIPTION,
        lifespan=lifespan,
        openapi_url=OPENAPI_URL,
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(data_router)

    @app.get(DOCS_URL, include_in_schema=False)
    async def docs() -> HTMLResponse:
        return get_scalar_api_reference(
            openapi_url=OPENAPI_URL,
            title=TITLE,
            telemetry=False,
            agent=AgentScalarConfig(disabled=True),
        )

    return app


app = create_app()
