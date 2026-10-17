"""What the backtests routes depend on: the service, on the request's Postgres session."""

from typing import Annotated

from fastapi import Depends

from candlestack.core import DbSessionDep
from candlestack.experiments.service import BacktestsService
from candlestack.experiments.store import BacktestStore


def get_backtests_service(db: DbSessionDep) -> BacktestsService:
    return BacktestsService(BacktestStore(db))


BacktestsServiceDep = Annotated[BacktestsService, Depends(get_backtests_service)]
