"""HTTP API of the data module: ``/api/v1/data/...`` and ``/api/health/sources``.

The routes validate parameters, ask the ``DataService`` and turn its errors into problem
details (docs/data.md, "Errors"). The service lives on ``app.state.data_service``.
"""

import logging
import math
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import AfterValidator, BeforeValidator, WithJsonSchema
from pydantic_core import PydanticCustomError

from candlestack.core import Problem, ProblemError, RateLimiter, SettingsDep
from candlestack.data.errors import (
    DataError,
    DataIntegrityError,
    InstrumentNotFound,
    InvalidRequest,
    PeriodOutOfRange,
    SourceUnavailable,
    TooManyCandles,
)
from candlestack.data.models import InstrumentId, Market, Timeframe
from candlestack.data.schemas import (
    CandlesOut,
    InstrumentDetailOut,
    InstrumentOut,
    InstrumentSearchOut,
    SourcesHealthOut,
    candles_json,
)
from candlestack.data.service import DataService

logger = logging.getLogger(__name__)

router = APIRouter()
data = APIRouter(prefix="/api/v1/data", tags=["data"])
health = APIRouter(tags=["health"])

# Patched by tests to move the clock.
_time = time.time
# 9999-12-31T23:59:59Z: a larger number is not epoch seconds (most likely milliseconds).
_MAX_EPOCH = 253402300799
_DIGITS = re.compile(r"[0-9]+")


def get_data_service(request: Request) -> DataService:
    return request.app.state.data_service


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


DataServiceDep = Annotated[DataService, Depends(get_data_service)]
RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]


def _instrument_id(value: str) -> str:
    try:
        return str(InstrumentId.parse(value))
    except InvalidRequest as error:
        raise PydanticCustomError("instrument_id", "{reason}", {"reason": error.detail}) from None


def _epoch_seconds(value: Any) -> Any:
    """Epoch seconds from digits or an ISO 8601 date or date-time (without offset: UTC)."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if _DIGITS.fullmatch(text):
        seconds = int(text)
        if seconds > _MAX_EPOCH:
            raise PydanticCustomError(
                "epoch_seconds",
                "{value} is after the year 9999: send epoch seconds, not milliseconds",
                {"value": text},
            )
        return seconds
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        hint = " (in a URL, write + as %2B)" if " " in text else ""
        raise PydanticCustomError(
            "time",
            "'{value}' is neither epoch seconds nor an ISO 8601 date or date-time{hint}",
            {"value": text, "hint": hint},
        ) from None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return math.floor(moment.timestamp())


InstrumentParam = Annotated[str, AfterValidator(_instrument_id)]
TIME_SCHEMA = {
    "anyOf": [{"type": "integer", "minimum": 0}, {"type": "string", "format": "date-time"}],
    "examples": ["2024-06-03", "2024-06-03T13:30:00Z", 1717421400],
}
TimeParam = Annotated[int, BeforeValidator(_epoch_seconds), WithJsonSchema(TIME_SCHEMA)]


@contextmanager
def _problems() -> Iterator[None]:
    """Raises the data module's errors inside the block as problem details."""
    try:
        yield
    except DataError as error:
        problem = _problem(error)
        if problem is None:
            raise
        raise problem from error


def _problem(error: DataError) -> ProblemError | None:
    detail = error.detail
    match error:
        case InstrumentNotFound():
            return ProblemError(
                404,
                "instrument-not-found",
                "Instrument not found",
                detail,
                extensions={"instrument": error.instrument},
            )
        case PeriodOutOfRange():
            return ProblemError(
                422,
                "period-out-of-range",
                "Period out of range",
                detail,
                extensions={
                    "instrument": error.instrument,
                    "timeframe": error.timeframe,
                    "available_from": error.available_from,
                    "available_to": error.available_to,
                },
            )
        case TooManyCandles():
            return ProblemError(
                422,
                "too-many-candles",
                "Too many candles",
                detail,
                extensions={
                    "requested": error.requested,
                    "maximum": error.maximum,
                    "suggestion": error.suggestion,
                },
            )
        case InvalidRequest():
            return ProblemError(422, "validation", "Invalid request", detail)
        case SourceUnavailable():
            headers = {}
            if error.retry_after is not None:
                headers["Retry-After"] = str(max(1, error.retry_after))
            return ProblemError(
                503,
                "source-unavailable",
                "Data source unavailable",
                detail,
                headers=headers,
                extensions={"source": error.source},
            )
        case DataIntegrityError():
            logger.error("Invalid data from %s: %s", error.source or "a source", detail)
            return ProblemError(
                502,
                "source-data-invalid",
                "Invalid data from the source",
                detail,
                extensions={"source": error.source},
            )
    return None


def _client_address(request: Request) -> str:
    """The client's IP: Cloudflare's ``CF-Connecting-IP``, else the peer (local runs)."""
    address = request.headers.get("cf-connecting-ip")
    if not address and request.client:
        address = request.client.host
    return address or "unknown"


async def client_rate_limit(
    request: Request, settings: SettingsDep, limiter: RateLimiterDep
) -> None:
    """``CLIENT_RATE_LIMIT`` candle requests per minute (UTC) and client IP; 429 beyond it.

    The counter is ``data:rl:client:<ip>:<minute>``; without Redis the limiter lets requests
    through.
    """
    limit = settings.client_rate_limit
    wait = await limiter.hit(f"data:rl:client:{_client_address(request)}", limit)
    if wait > 0:
        retry = max(1, math.ceil(wait))
        raise ProblemError(
            429,
            "rate-limited",
            "Too many requests",
            f"More than {limit} candle requests in one minute from this address. "
            f"Retry in {retry} seconds.",
            headers={"Retry-After": str(retry)},
            extensions={"limit": limit},
        )


def _errors(descriptions: dict[int, str]) -> dict[int | str, dict[str, Any]]:
    """OpenAPI error responses of a route, each a problem with the given description."""
    return {
        status: {"model": Problem, "description": description}
        for status, description in descriptions.items()
    }


_SOURCE_ERRORS = {
    502: "The source sent data that failed validation (`source-data-invalid`).",
    503: "The source is down or our request budget for it is spent (`source-unavailable`); "
    "`Retry-After` when waiting helps.",
}


@data.get(
    "/instruments",
    summary="Search instruments",
    responses=_errors({422: "Invalid parameters (`validation`).", **_SOURCE_ERRORS}),
)
async def search_instruments(
    service: DataServiceDep,
    q: Annotated[
        str,
        Query(
            min_length=1,
            max_length=50,
            description="Symbol or name, case-insensitive; separators in symbols are ignored "
            "(`btc/usdt` finds `BTCUSDT`, `brkb` finds `BRK.B`).",
            examples=["btc"],
        ),
    ],
    market: Annotated[Market | None, Query(description="Only this market.")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Most items to return.")] = 20,
) -> InstrumentSearchOut:
    """Searches the instruments of both markets: every Binance spot pair that is trading and
    every active tradable US stock and ETF at Alpaca (without OTC).

    Ranking: exact symbol, symbol prefix, prefix of a word in the name, substring of the
    symbol, substring of the name; ties go to the shorter symbol, then alphabetically.
    """
    with _problems():
        found = await service.search(q, market, limit)
    return InstrumentSearchOut(items=[InstrumentOut.of(item) for item in found], count=len(found))


@data.get(
    "/instruments/{instrument_id}",
    summary="Instrument detail",
    responses=_errors(
        {
            404: "The instrument is not in the catalog (`instrument-not-found`).",
            422: "Malformed instrument id (`validation`).",
            **_SOURCE_ERRORS,
        }
    ),
)
async def instrument_detail(
    service: DataServiceDep,
    instrument_id: Annotated[
        InstrumentParam,
        Path(description="Instrument id, `<market>:<symbol>`.", examples=["crypto:BTCUSDT"]),
    ],
) -> InstrumentDetailOut:
    """An instrument with its timeframes, available period and the candle limit: what a valid
    `/candles` request can ask for."""
    with _problems():
        info = await service.instrument(InstrumentId.parse(instrument_id))
    return InstrumentDetailOut.of_info(info)


@data.get(
    "/candles",
    summary="Candles",
    response_model=CandlesOut,
    dependencies=[Depends(client_rate_limit)],
    responses=_errors(
        {
            404: "The instrument is not in the catalog (`instrument-not-found`).",
            422: "Invalid parameters (`validation`), a period outside the available data "
            "(`period-out-of-range`) or more candles than `max_candles` (`too-many-candles`).",
            429: "More candle requests from this address than the per-minute limit "
            "(`rate-limited`); see `Retry-After`.",
            **_SOURCE_ERRORS,
        }
    ),
)
async def candles(
    service: DataServiceDep,
    instrument: Annotated[
        InstrumentParam,
        Query(description="Instrument id, `<market>:<symbol>`.", examples=["crypto:BTCUSDT"]),
    ],
    timeframe: Annotated[Timeframe, Query(examples=["1h"])],
    start: Annotated[
        TimeParam,
        Query(
            description="Start of the period, inclusive: UTC epoch seconds or ISO 8601 "
            "(`2024-06-03`, `2024-06-03T13:30:00Z`; without an offset it is UTC).",
        ),
    ],
    end: Annotated[
        TimeParam | None,
        Query(
            description="End of the period, exclusive, in the same formats; default now.",
            examples=["2024-06-04"],
        ),
    ] = None,
) -> Response:
    """Closed candles of one instrument and timeframe with `start <= t < end`.

    Stocks have regular-session candles only (09:30-16:00 New York), aligned to the session
    open. Missing candles are never filled; `meta.gaps` reports them. Limits: `max_candles`
    expected candles per request (see the instrument detail) and a per-minute number of
    requests per client address.
    """
    now = end is None
    if end is None:
        end = int(_time())
    if start >= end:
        raise RequestValidationError(
            [
                {
                    "type": "period",
                    "loc": ("query", "end"),
                    "msg": f"end ({end}{', now' if now else ''}) must be after start ({start})",
                    "input": end,
                }
            ]
        )
    with _problems():
        found = await service.candles(InstrumentId.parse(instrument), timeframe, start, end)
    return Response(candles_json(found), media_type="application/json")


@health.get(
    "/api/health/sources",
    summary="Health of the data sources",
    responses={503: {"model": SourcesHealthOut, "description": "A source is unreachable"}},
)
async def sources_health(service: DataServiceDep, response: Response) -> SourcesHealthOut:
    """Reachability of Binance (`GET /api/v3/ping`) and Alpaca (`GET /v2/clock`), checked at
    most once a minute. 200 when both answer, 503 with the same body when one does not."""
    body = SourcesHealthOut.of(await service.sources_health())
    if body.status != "ok":
        response.status_code = 503
    return body


router.include_router(data)
router.include_router(health)
