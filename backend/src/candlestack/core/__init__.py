"""Shared foundations of every module: settings, logging, errors, Redis, outgoing HTTP, health.

Other modules import only from here (``from candlestack.core import ProblemError``), never
from the submodules.
"""

from candlestack.core.config import Settings, SettingsDep, get_settings
from candlestack.core.errors import (
    Problem,
    ProblemError,
    document_problems,
    install_error_handlers,
    problem_responses,
)
from candlestack.core.health import router as health_router
from candlestack.core.http import (
    HttpClientDep,
    create_http_client,
    request_with_retry,
    retry_after,
)
from candlestack.core.logging import setup_logging
from candlestack.core.middleware import RequestContextMiddleware
from candlestack.core.redis import RedisDep, create_redis

__all__ = [
    "HttpClientDep",
    "Problem",
    "ProblemError",
    "RedisDep",
    "RequestContextMiddleware",
    "Settings",
    "SettingsDep",
    "create_http_client",
    "create_redis",
    "document_problems",
    "get_settings",
    "health_router",
    "install_error_handlers",
    "problem_responses",
    "request_with_retry",
    "retry_after",
    "setup_logging",
]
