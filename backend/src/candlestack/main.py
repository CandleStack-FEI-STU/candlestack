"""The CandleStack API app, served by granian: ``candlestack.main:app``."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from scalar_fastapi import AgentScalarConfig, get_scalar_api_reference

from candlestack.core import (
    RateLimiter,
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
# The icon is served by the frontend on the same host, like the rest of the site.
ICON_URL = "/favicon.svg"
DESCRIPTION = (
    f'<img src="{ICON_URL}" alt="CandleStack" width="40" height="40">\n\n'
    "HTTP API of CandleStack, a lab for experiments on financial time series. "
    "Market data covers crypto from Binance and US stocks from Alpaca. "
    "Times in responses are UTC epoch seconds; requests also accept ISO 8601. "
    "Errors are RFC 9457 problem details (`application/problem+json`).\n\n"
    "[Website](https://candlestack.tech) · "
    "[Source code](https://github.com/CandleStack-FEI-STU/candlestack) · "
    "[Status](https://ops.candlestack.tech)"
)
OPENAPI_URL = "/api/v1/openapi.json"
DOCS_URL = "/api/v1/docs"
# A relative server makes the code examples use the host the docs are opened on.
SERVERS = [{"url": "/", "description": "This environment"}]
# Scalar has no option for its footer link, so CSS hides it.
DOCS_CSS = 'a[href^="https://www.scalar.com"] { display: none !important; }'


class CandleStackAPI(FastAPI):
    def openapi(self) -> dict[str, Any]:
        if self.openapi_schema is None:
            self.openapi_schema = document_problems(super().openapi())
        return self.openapi_schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Opens the shared clients on ``app.state`` (``redis``, ``http``) and builds what uses
    them: the client ``rate_limiter`` and the market ``data_service``."""
    settings: Settings = app.state.settings
    app.state.redis = create_redis(settings.redis_url)
    app.state.rate_limiter = RateLimiter(app.state.redis)
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
        servers=SERVERS,
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
            scalar_favicon_url=ICON_URL,
            document_download_type="none",
            show_developer_tools="never",
            custom_css=DOCS_CSS,
            telemetry=False,
            agent=AgentScalarConfig(disabled=True),
            overrides={"mcp": {"disabled": True}},
        )

    return app


app = create_app()
