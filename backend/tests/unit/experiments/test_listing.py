"""How the list's search, filters, sorts and pages turn into SQL, without a database; the
results are integration tests (tests/integration/experiments)."""

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from candlestack.experiments.models import Backtest, new_backtest_id
from candlestack.experiments.schemas import BacktestShow, BacktestSort, SortOrder
from candlestack.experiments.service import pages
from candlestack.experiments.store import (
    _reads_models,
    escape_like,
    filters,
    ordering,
    search,
)


def _after_from(query) -> str:
    compiled = query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    return str(compiled).split("FROM backtests", 1)[1].strip()


def where_sql(*conditions) -> str:
    """The WHERE of a query over the backtests, as Postgres gets it."""
    return _after_from(select(Backtest.id).where(*conditions))


def order_sql(*clauses) -> str:
    """The ORDER BY of a query over the backtests, as Postgres gets it."""
    return _after_from(select(Backtest.id).order_by(*clauses))


@pytest.mark.parametrize(
    ("value", "escaped"),
    [("aapl", "aapl"), ("50%", "50\\%"), ("a_b", "a\\_b"), ("c:\\x", "c:\\\\x")],
)
def test_escape_like(value: str, escaped: str) -> None:
    assert escape_like(value) == escaped


@pytest.mark.parametrize("query", ["", "   "])
def test_a_blank_search_matches_everything(query: str) -> None:
    assert search(query) is None
    assert filters(query=query) == []


def test_search_looks_at_the_number_the_symbols_and_the_models_name() -> None:
    condition = search(" Aapl ")
    assert condition is not None

    sql = where_sql(condition)

    assert "('#' || CAST(backtests.number AS VARCHAR)) ILIKE '%%Aapl%%' ESCAPE" in sql
    assert "jsonb_array_elements(backtests.instruments)" in sql
    assert "coalesce(models.name, backtests.model_name) ILIKE '%%Aapl%%'" in sql


def test_the_filters_add_up() -> None:
    conditions = filters(query="12", show=BacktestShow.starred, model="Lstm.keras")

    sql = where_sql(*conditions)

    assert len(conditions) == 3
    assert "backtests.starred IS true" in sql
    assert "lower(coalesce(models.name, backtests.model_name)) = lower('Lstm.keras')" in sql


def test_show_failed() -> None:
    assert where_sql(*filters(show=BacktestShow.failed)) == "WHERE backtests.status = 'failed'"


def test_show_all_filters_nothing() -> None:
    assert filters(show=BacktestShow.all) == []


@pytest.mark.parametrize("order", list(SortOrder))
def test_the_default_sort_is_newest_first_in_any_order(order: SortOrder) -> None:
    assert order_sql(*ordering(BacktestSort.default, order)) == (
        "ORDER BY backtests.created_at DESC, backtests.number DESC"
    )


@pytest.mark.parametrize(
    ("sort", "order", "expected"),
    [
        (BacktestSort.sharpe, SortOrder.desc, "backtests.sharpe DESC NULLS LAST"),
        (BacktestSort.sharpe, SortOrder.asc, "backtests.sharpe ASC NULLS LAST"),
        (BacktestSort.total_return, SortOrder.asc, "backtests.total_return ASC NULLS LAST"),
        (BacktestSort.max_drawdown, SortOrder.desc, "backtests.max_drawdown DESC NULLS LAST"),
        (BacktestSort.trades, SortOrder.desc, "backtests.num_trades DESC NULLS LAST"),
        (BacktestSort.number, SortOrder.asc, "backtests.number ASC NULLS LAST"),
        (BacktestSort.when, SortOrder.asc, "backtests.number ASC NULLS LAST"),
        (
            BacktestSort.model,
            SortOrder.asc,
            "lower(coalesce(models.name, backtests.model_name)) ASC NULLS LAST",
        ),
    ],
)
def test_a_sort_puts_nulls_last_and_ties_newest_first(
    sort: BacktestSort, order: SortOrder, expected: str
):
    assert order_sql(*ordering(sort, order)) == f"ORDER BY {expected}, backtests.number DESC"


def test_only_the_search_and_the_model_filter_read_the_models() -> None:
    assert _reads_models(filters(query="aapl")) is True
    assert _reads_models(filters(model="lstm.keras")) is True
    assert _reads_models(filters(show=BacktestShow.starred)) is False
    assert _reads_models(filters(show=BacktestShow.failed)) is False
    assert _reads_models([]) is False


@pytest.mark.parametrize(("total", "expected"), [(0, 1), (1, 1), (10, 1), (11, 2), (23, 3)])
def test_pages(total: int, expected: int) -> None:
    assert pages(total) == expected


def test_backtest_ids() -> None:
    ids = {new_backtest_id() for _ in range(100)}

    assert len(ids) == 100
    for backtest_id in ids:
        assert backtest_id.startswith("bt_")
        assert len(backtest_id) == 13
        assert set(backtest_id[3:]) <= set("abcdefghijklmnopqrstuvwxyz234567")
