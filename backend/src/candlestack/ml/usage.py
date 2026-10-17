"""How much the backtests used each model. Backtests live in ``experiments``, which imports
``ml``, so ``ml`` cannot ask them itself: ``candlestack.main`` hands it a ``ModelUsage`` on
``app.state.model_usage``. Without one (``no_usage``) every model reads as never used."""

from collections.abc import Mapping, Sequence
from typing import NamedTuple, Protocol

from sqlalchemy.ext.asyncio import AsyncSession


class ModelUsageStats(NamedTuple):
    backtest_count: int
    best_sharpe: float | None


UNUSED = ModelUsageStats(backtest_count=0, best_sharpe=None)


class ModelUsage(Protocol):
    """The usage of the user's models with the IDs, in the request's session: one query for all
    of them, never one per model. A model no backtest used may be left out."""

    async def __call__(
        self, db: AsyncSession, user_id: str, model_ids: Sequence[str], /
    ) -> Mapping[str, ModelUsageStats]: ...


async def no_usage(
    _db: AsyncSession, _user_id: str, _model_ids: Sequence[str], /
) -> Mapping[str, ModelUsageStats]:
    return {}
