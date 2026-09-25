"""RFC 9457 problem details: the body of every error response of the API.

Raise ``ProblemError`` from any route or dependency; ``install_error_handlers`` turns it, request
validation errors, HTTP errors of the framework and unhandled exceptions into
``application/problem+json`` responses.
"""

import logging
from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Any

import orjson
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException

PROBLEM_TYPE_BASE = "https://candlestack.tech/problems/"
PROBLEM_MEDIA_TYPE = "application/problem+json"
_MEMBERS = frozenset({"type", "title", "status", "detail"})

logger = logging.getLogger(__name__)


class Problem(BaseModel):
    """Error response (RFC 9457). Some problems add members, such as `errors` on 422."""

    model_config = ConfigDict(extra="allow")

    type: str = Field(examples=[f"{PROBLEM_TYPE_BASE}validation"])
    title: str = Field(examples=["Invalid request"])
    status: int = Field(examples=[422])
    detail: str = Field(examples=["query parameter 'limit': Input should be at most 100"])


class ProblemResponse(Response):
    media_type = PROBLEM_MEDIA_TYPE

    def render(self, content: Any) -> bytes:
        return orjson.dumps(content)


class ProblemError(Exception):
    """An error the client should see, answered with a problem+json response.

    `slug` names the problem type (``https://candlestack.tech/problems/<slug>``), `title` is its
    short fixed summary and `detail` tells the user what happened and what to do, e.g.
    ``ProblemError(429, "rate-limited", "Too many requests", "... try again in 12 s.",
    headers={"Retry-After": "12"}, extensions={"limit": 60})``.
    """

    def __init__(
        self,
        status: int,
        slug: str,
        title: str,
        detail: str,
        *,
        headers: Mapping[str, str] | None = None,
        extensions: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        reserved = _MEMBERS.intersection(extensions or {})
        if reserved:
            raise ValueError(f"Problem extensions must not redefine {sorted(reserved)}")
        self.status = status
        self.slug = slug
        self.title = title
        self.detail = detail
        self.headers = dict(headers or {})
        self.extensions = dict(extensions or {})


def problem_response(
    status: int,
    slug: str,
    title: str,
    detail: str,
    *,
    headers: Mapping[str, str] | None = None,
    extensions: Mapping[str, Any] | None = None,
) -> ProblemResponse:
    body = {"type": PROBLEM_TYPE_BASE + slug, "title": title, "status": status, "detail": detail}
    body.update(extensions or {})
    return ProblemResponse(body, status_code=status, headers=headers)


def internal_error_response() -> ProblemResponse:
    """The 500 answer to an unhandled exception: nothing about the cause leaks to the client."""
    return problem_response(
        500,
        "internal-error",
        "Internal server error",
        "The server failed to handle this request. Try again later; if it keeps failing, "
        "report the X-Request-ID header of this response.",
    )


def problem_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """Documents error statuses of a route in OpenAPI: ``@router.get(..., responses=...)``."""
    return {
        status: {"model": Problem, "description": HTTPStatus(status).phrase} for status in statuses
    }


async def _problem_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, ProblemError)
    return problem_response(
        exc.status,
        exc.slug,
        exc.title,
        exc.detail,
        headers=exc.headers,
        extensions=exc.extensions,
    )


async def _validation_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    raw = exc.errors()
    return problem_response(
        422,
        "validation",
        "Invalid request",
        "; ".join(_describe(error["loc"], error["msg"]) for error in raw),
        extensions={
            "errors": [
                {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
                for error in raw
            ]
        },
    )


def _describe(loc: Sequence[Any], msg: str) -> str:
    where, *path = loc
    name = ".".join(str(part) for part in path)
    return f"{where} parameter {name!r}: {msg}" if name else f"{where}: {msg}"


async def _http_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, HTTPException)
    status = HTTPStatus(exc.status_code)
    detail = str(exc.detail)
    if detail == status.phrase:  # the framework's own errors say no more than the title
        if status == HTTPStatus.NOT_FOUND:
            detail = f"Nothing at {request.url.path}. The API reference is at /api/v1/docs."
        elif status == HTTPStatus.METHOD_NOT_ALLOWED and exc.headers:
            allowed = exc.headers.get("Allow", "")
            detail = f"{request.method} is not allowed on {request.url.path}; use {allowed}."
    return problem_response(
        status.value,
        status.phrase.lower().replace(" ", "-"),
        status.phrase,
        detail,
        headers=exc.headers,
    )


async def _unhandled_error(request: Request, exc: Exception) -> Response:
    logger.error("Unhandled error", exc_info=exc)
    return internal_error_response()


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ProblemError, _problem_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(Exception, _unhandled_error)


def document_problems(schema: dict[str, Any]) -> dict[str, Any]:
    """Rewrites a generated OpenAPI schema so its error responses say what the API sends.

    FastAPI documents every error model as ``application/json`` and adds its own 422 model to
    each route with parameters; the API answers all of them with ``application/problem+json``.
    """
    schemas = schema.setdefault("components", {}).setdefault("schemas", {})
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)
    schemas["Problem"] = Problem.model_json_schema(
        ref_template="#/components/schemas/{model}", mode="serialization"
    )
    for operations in schema.get("paths", {}).values():
        for operation in operations.values():
            for code, response in operation.get("responses", {}).items():
                media = response.get("content", {}).get("application/json", {})
                ref = media.get("schema", {}).get("$ref", "")
                if ref.endswith(("/Problem", "/HTTPValidationError")):
                    response["content"] = {
                        PROBLEM_MEDIA_TYPE: {"schema": {"$ref": "#/components/schemas/Problem"}}
                    }
                    if code == "422":
                        response["description"] = "Invalid request"
    return schema
