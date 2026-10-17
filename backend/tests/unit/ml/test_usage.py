"""What the models list shows of their backtests without anything that counts them."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from candlestack.ml import no_usage
from candlestack.ml.store import ModelStore


@pytest.mark.anyio
async def test_without_a_usage_no_model_was_used() -> None:
    assert await no_usage(AsyncSession(), "usr_7f3k2m9qx4", ["mdl_7f3k2m9qx4"]) == {}


@pytest.mark.anyio
async def test_a_store_asks_no_usage_of_no_models() -> None:
    async def fail(*_args):
        raise AssertionError("asked for no models")

    store = ModelStore(AsyncSession(), fail)

    assert await store.backtest_usage("usr_7f3k2m9qx4", []) == {}
