# ruff: noqa: ARG001 (scaffold: the bodies come with the implementation, which drops this line)
"""HTTP API of the ml module: the signed-in user's models under ``/api/v1/models``.

An upload is the file itself as the request body (``application/octet-stream``) with its name
in ``?name=``, so the server streams it to disk instead of holding a multipart form in memory.
It runs two checks on the file, ``opens`` and ``weights`` (``ModelCheck``), without executing
anything from it; a failed check answers 422 ``model-check-failed`` naming the check.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request, Response

from candlestack.accounts import CurrentUserDep
from candlestack.core import Problem, require_same_origin
from candlestack.ml.schemas import ModelOut, ModelsOut, ModelUpdate

router = APIRouter(tags=["models"])

# What the responses about the user's models carry must not be kept by a browser cache or a proxy.
NO_STORE = {"Cache-Control": "no-store"}

ModelId = Annotated[str, Path(description="Public ID of the model", examples=["mdl_7f3k2m9qx4"])]
FileName = Annotated[
    str,
    Query(
        min_length=1,
        max_length=255,
        description="Name of the uploaded file, extension included",
        examples=["lstm-signals.keras"],
    ),
]


def _problem(status: int, description: str) -> dict[int | str, dict[str, Any]]:
    """An OpenAPI error response of a route: a problem with the given description."""
    return {status: {"model": Problem, "description": description}}


_NOT_SIGNED_IN = _problem(401, "Not signed in (`not-signed-in`).")
_CROSS_ORIGIN = _problem(
    403, "The request does not come from the app's own pages (`cross-origin-request`)."
)
_NOT_FOUND = _problem(404, "The user has no model with this ID (`not-found`).")
_UPLOAD_BODY = {
    "requestBody": {
        "required": True,
        "description": "The model file",
        "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
    }
}


@router.get("/api/v1/models", responses=_NOT_SIGNED_IN)
async def list_models(user: CurrentUserDep, response: Response) -> ModelsOut:
    """The user's uploaded models, oldest first, and the storage they take."""
    response.headers.update(NO_STORE)
    raise NotImplementedError


@router.post(
    "/api/v1/models",
    status_code=201,
    responses={
        **_NOT_SIGNED_IN,
        **_CROSS_ORIGIN,
        **_problem(
            409,
            "The file does not fit into the user's storage (`storage-full`); `used_bytes` and "
            "`quota_bytes` say how much is taken.",
        ),
        **_problem(413, "The file is larger than 50 MB (`model-too-large`)."),
        **_problem(
            415,
            "Not a format the app takes yet, only Keras (`.keras`) for now "
            "(`unsupported-model-format`).",
        ),
        **_problem(
            422,
            "A check failed (`model-check-failed`): `check` names it (`opens` or `weights`) and "
            "`detail` says why; or the request is invalid (`validation`).",
        ),
    },
    dependencies=[Depends(require_same_origin)],
    openapi_extra=_UPLOAD_BODY,
)
async def upload_model(
    name: FileName, request: Request, user: CurrentUserDep, response: Response
) -> ModelOut:
    """Uploads a model file: the body is the file, `name` its file name. The file is checked
    before it is kept: `opens` (a real Keras model with no custom code inside, nothing from
    the file is executed) and `weights` (it holds trained weights). A file with a name the user
    already has gets a number, as `lstm (2).keras`."""
    response.headers.update(NO_STORE)
    raise NotImplementedError


@router.patch(
    "/api/v1/models/{model_id}",
    responses={
        **_NOT_SIGNED_IN,
        **_CROSS_ORIGIN,
        **_NOT_FOUND,
        **_problem(409, "The user has another model with this name (`model-name-taken`)."),
    },
    dependencies=[Depends(require_same_origin)],
)
async def update_model(
    model_id: ModelId, body: ModelUpdate, user: CurrentUserDep, response: Response
) -> ModelOut:
    """Renames the model (the extension stays) or stars and unstars it."""
    response.headers.update(NO_STORE)
    raise NotImplementedError


@router.delete(
    "/api/v1/models/{model_id}",
    status_code=204,
    responses={**_NOT_SIGNED_IN, **_CROSS_ORIGIN, **_NOT_FOUND},
    dependencies=[Depends(require_same_origin)],
)
async def delete_model(model_id: ModelId, user: CurrentUserDep) -> None:
    """Deletes the model and its file, which frees its storage."""
    raise NotImplementedError
