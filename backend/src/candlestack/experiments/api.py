"""HTTP API of the experiments module: the signed-in user's backtests under
``/api/v1/backtests`` and the Dashboard under ``/api/v1/dashboard``.

Backtests are not made over the API yet: the backtest builder comes later.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Response

from candlestack.accounts import CurrentUserDep
from candlestack.core import Problem, ProblemError, require_same_origin
from candlestack.experiments.dependencies import BacktestsServiceDep
from candlestack.experiments.errors import BacktestNotFound
from candlestack.experiments.schemas import (
    PAGE_SIZE,
    QUERY_MAX,
    BacktestOut,
    BacktestShow,
    BacktestSort,
    BacktestsPage,
    BacktestUpdate,
    DashboardOut,
    SortOrder,
)
from candlestack.experiments.service import ListQuery

router = APIRouter(tags=["backtests"])

# What the responses about the user's backtests carry must not be kept by a browser cache or a
# proxy.
NO_STORE = {"Cache-Control": "no-store"}
# A page number far past any user's backtests; the limit keeps the offset a small integer.
PAGE_MAX = 100_000

BacktestId = Annotated[
    str, Path(description="Public ID of the backtest", examples=["bt_7f3k2m9qx4"])
]


def _problem(status: int, description: str) -> dict[int | str, dict[str, Any]]:
    """An OpenAPI error response of a route: a problem with the given description."""
    return {status: {"model": Problem, "description": description}}


_NOT_SIGNED_IN = _problem(401, "Not signed in (`not-signed-in`).")


def list_query(
    *,
    q: Annotated[
        str,
        Query(
            max_length=QUERY_MAX,
            description=(
                "Search: part of the number (`#12` or `12`), of an instrument's symbol or of the "
                "model's name, in any case"
            ),
            examples=["aapl"],
        ),
    ] = "",
    show: Annotated[
        BacktestShow, Query(description="All, the starred or the failed backtests")
    ] = BacktestShow.all,
    model: Annotated[
        str | None,
        Query(
            max_length=255,
            description="Only the backtests of the model with this name, in any case",
            examples=["blesk-novol-8.keras"],
        ),
    ] = None,
    sort: Annotated[BacktestSort, Query(description="What to sort by")] = BacktestSort.default,
    order: Annotated[SortOrder, Query(description="SetupDirection of the sort")] = SortOrder.desc,
    page: Annotated[
        int, Query(ge=1, le=PAGE_MAX, description=f"The page, from 1, of {PAGE_SIZE} backtests")
    ] = 1,
) -> ListQuery:
    return ListQuery(query=q, show=show, model=model, sort=sort, order=order, page=page)


@router.get("/api/v1/backtests", responses=_NOT_SIGNED_IN)
async def list_backtests(
    query: Annotated[ListQuery, Depends(list_query)],
    user: CurrentUserDep,
    service: BacktestsServiceDep,
    response: Response,
) -> BacktestsPage:
    """A page of the user's backtests that match the search and the filters, and what the
    filter panel shows: the counts of all, starred and failed backtests and every model the
    backtests used. A page past the last one is empty."""
    response.headers.update(NO_STORE)
    return await service.backtests(user.id, query)


@router.patch(
    "/api/v1/backtests/{backtest_id}",
    responses={
        **_NOT_SIGNED_IN,
        **_problem(
            403, "The request does not come from the app's own pages (`cross-origin-request`)."
        ),
        **_problem(404, "The user has no backtest with this ID (`not-found`)."),
    },
    dependencies=[Depends(require_same_origin)],
)
async def update_backtest(
    backtest_id: BacktestId,
    body: BacktestUpdate,
    user: CurrentUserDep,
    service: BacktestsServiceDep,
    response: Response,
) -> BacktestOut:
    """Stars or unstars the backtest."""
    response.headers.update(NO_STORE)
    try:
        return await service.star(user.id, backtest_id, starred=body.starred)
    except BacktestNotFound:
        raise ProblemError(
            404, "not-found", "Not Found", "You have no backtest with this ID."
        ) from None


@router.get("/api/v1/dashboard", responses=_NOT_SIGNED_IN)
async def dashboard(
    user: CurrentUserDep, service: BacktestsServiceDep, response: Response
) -> DashboardOut:
    """Everything the Dashboard shows: the counts of the user's backtests, the newest ones,
    the best finished ones by Sharpe ratio, return, drawdown and win rate, and the best
    starred ones."""
    response.headers.update(NO_STORE)
    return await service.dashboard(user.id)
