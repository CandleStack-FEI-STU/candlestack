"""What the models routes depend on: the service, on the request's Postgres session and the
app's model storage."""

from typing import Annotated

from fastapi import Depends, Request

from candlestack.core import DbSessionDep
from candlestack.ml.service import ModelsService
from candlestack.ml.storage import ModelStorage
from candlestack.ml.store import ModelStore


def get_model_storage(request: Request) -> ModelStorage:
    """The storage ``candlestack.main`` puts on the app."""
    return request.app.state.model_storage


def get_models_service(
    db: DbSessionDep, storage: Annotated[ModelStorage, Depends(get_model_storage)]
) -> ModelsService:
    return ModelsService(ModelStore(db), storage)


ModelsServiceDep = Annotated[ModelsService, Depends(get_models_service)]
