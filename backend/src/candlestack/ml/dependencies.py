"""What the models routes depend on: the service, on the request's Postgres session, Redis
(the upload locks), the app's model storage and what counts the models' backtests."""

from typing import Annotated

from fastapi import Depends, Request

from candlestack.core import DbSessionDep, RedisDep
from candlestack.ml.service import ModelsService
from candlestack.ml.storage import ModelStorage
from candlestack.ml.store import ModelStore
from candlestack.ml.uploads import RedisUploadLocks
from candlestack.ml.usage import ModelUsage


def get_model_storage(request: Request) -> ModelStorage:
    """The storage ``candlestack.main`` puts on the app."""
    return request.app.state.model_storage


def get_model_usage(request: Request) -> ModelUsage:
    """The usage ``candlestack.main`` puts on the app (``experiments`` counts the backtests)."""
    return request.app.state.model_usage


def get_models_service(
    db: DbSessionDep,
    redis: RedisDep,
    storage: Annotated[ModelStorage, Depends(get_model_storage)],
    usage: Annotated[ModelUsage, Depends(get_model_usage)],
) -> ModelsService:
    return ModelsService(ModelStore(db, usage), storage, RedisUploadLocks(redis))


ModelsServiceDep = Annotated[ModelsService, Depends(get_models_service)]
