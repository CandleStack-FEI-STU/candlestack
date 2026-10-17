"""The models of a user: uploading a file, listing, renaming, starring and deleting them, and
deleting them with the account.

An upload streams to an incoming file of the storage while it is counted and hashed, never
held in memory, and is checked there (``inspect.py``) in a worker thread. Only a file that
passed is kept: in one transaction under the lock of the user's models, so two uploads cannot
both pass the quota or take the same name, its row goes in and the file moves to its place;
the file goes again when the commit fails. The incoming files are removed whatever happens.
"""

import hashlib
import logging
import re
from collections.abc import AsyncIterable
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

import anyio
from sqlalchemy.ext.asyncio import AsyncSession

from candlestack.accounts import AfterDeletion
from candlestack.ml.errors import (
    ModelCheckFailed,
    ModelNameTaken,
    ModelNotFound,
    ModelTooLarge,
    StorageFull,
    UnsupportedModelFormat,
)
from candlestack.ml.inspect import ModelFacts, inspect_keras
from candlestack.ml.models import Model, new_model_id
from candlestack.ml.schemas import (
    FILE_MAX_BYTES,
    NAME_MAX,
    QUOTA_BYTES,
    Framework,
    ModelCheck,
    ModelOut,
    ModelsOut,
    ModelUpdate,
    StorageUsage,
)
from candlestack.ml.storage import ModelStorage
from candlestack.ml.store import ModelStore

logger = logging.getLogger(__name__)

KERAS_SUFFIX = ".keras"
# The name a file without a usable one gets (".keras").
DEFAULT_STEM = "model"
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_EMPTY = "The file is empty. Choose the model's .keras file and upload it again."


def _now() -> datetime:
    return datetime.now(UTC)


def upload_name(file_name: str) -> str:
    """The name an uploaded file is kept under: its base name (a client may send a path)
    without control characters, the part before the extension cut to what Rename saves.

    Raises:
        UnsupportedModelFormat: Not a Keras file (``.keras``, in any case).
    """
    base = file_name.replace("\\", "/").rsplit("/", 1)[-1]
    if not base.lower().endswith(KERAS_SUFFIX):
        raise UnsupportedModelFormat
    stem, suffix = _split(base)
    stem = _CONTROL.sub("", stem).strip()[:NAME_MAX].rstrip()
    return (stem or DEFAULT_STEM) + suffix


def numbered(name: str, number: int) -> str:
    """`name` with `number` before its extension, ``lstm (2).keras``; the first is `name`.
    The part before the extension stays within what Rename saves."""
    if number == 1:
        return name
    stem, suffix = _split(name)
    label = f" ({number})"
    return stem[: NAME_MAX - len(label)].rstrip() + label + suffix


def _split(name: str) -> tuple[str, str]:
    """A model's name as the part Rename changes and the extension, which stays."""
    return name[: -len(KERAS_SUFFIX)], name[-len(KERAS_SUFFIX) :]


def _out(model: Model) -> ModelOut:
    return ModelOut(
        id=model.id,
        name=model.name,
        framework=Framework(model.framework),
        size_bytes=model.size_bytes,
        parameters=model.parameters,
        input_shape=model.input_shape,
        output_shape=model.output_shape,
        starred=model.starred,
        # Backtests come with the next milestone.
        backtest_count=0,
        best_sharpe=None,
        created_at=model.created_at,
    )


async def _receive(chunks: AsyncIterable[bytes], path: Path) -> tuple[int, bytes]:
    """Writes the uploaded file to `path`; its size and SHA-256.

    Raises:
        ModelTooLarge: It is larger than an upload may be (it stops reading there).
        ModelCheckFailed: It is empty.
    """
    digest = hashlib.sha256()
    size = 0
    async with await anyio.open_file(path, "wb") as file:
        async for chunk in chunks:
            size += len(chunk)
            if size > FILE_MAX_BYTES:
                raise ModelTooLarge
            digest.update(chunk)
            await file.write(chunk)
    if size == 0:
        raise ModelCheckFailed(ModelCheck.opens, _EMPTY)
    return size, digest.digest()


class ModelsService:
    def __init__(self, store: ModelStore, storage: ModelStorage) -> None:
        self._store = store
        self._storage = storage

    async def models(self, user_id: str) -> ModelsOut:
        """The user's models, oldest first, and the storage they take."""
        models = await self._store.models(user_id)
        return ModelsOut(
            models=[_out(model) for model in models],
            usage=StorageUsage(
                used_bytes=sum(model.size_bytes for model in models),
                quota_bytes=QUOTA_BYTES,
                file_max_bytes=FILE_MAX_BYTES,
            ),
        )

    async def upload(
        self,
        user_id: str,
        file_name: str,
        declared_size: int | None,
        chunks: AsyncIterable[bytes],
    ) -> ModelOut:
        """Checks the uploaded file and keeps it as a model of the user. `declared_size` is the
        size the client announced (Content-Length), if any: one too large fails before anything
        is read.

        Raises:
            UnsupportedModelFormat: `file_name` is not that of a Keras file; nothing is read.
            ModelTooLarge: The file is larger than an upload may be.
            StorageFull: The file does not fit into the user's storage.
            ModelCheckFailed: The file failed a check.
        """
        name = upload_name(file_name)
        if declared_size is not None and declared_size > FILE_MAX_BYTES:
            raise ModelTooLarge
        used = await self._store.used_bytes(user_id)
        # Ends the transaction, so its connection goes back to the pool while the file comes in.
        await self._store.commit()
        if declared_size is not None and used + declared_size > QUOTA_BYTES:
            raise StorageFull(used, QUOTA_BYTES)
        incoming = self._storage.incoming_path()
        scratch = self._storage.incoming_path()
        try:
            size, sha256 = await _receive(chunks, incoming)
            facts = await anyio.to_thread.run_sync(inspect_keras, incoming, scratch)
            model = await self._keep(
                user_id, incoming, name=name, size=size, sha256=sha256, facts=facts
            )
        except ModelCheckFailed as failed:
            logger.info("An upload of user %s failed the %s check", user_id, failed.check)
            raise
        finally:
            await self._storage.discard(incoming)
            await self._storage.discard(scratch)
        logger.info("User %s uploaded model %s (%d bytes)", user_id, model.id, size)
        return _out(model)

    async def _keep(
        self,
        user_id: str,
        incoming: Path,
        *,
        name: str,
        size: int,
        sha256: bytes,
        facts: ModelFacts,
    ) -> Model:
        """Adds the model of a checked file and moves the file to its place, in one transaction
        under the lock of the user's models.

        Raises:
            StorageFull: The file does not fit into the user's storage.
        """
        await self._store.lock_user(user_id)
        used = await self._store.used_bytes(user_id)
        if used + size > QUOTA_BYTES:
            raise StorageFull(used, QUOTA_BYTES)
        model = Model(
            id=new_model_id(),
            user_id=user_id,
            name=await self._free_name(user_id, name),
            framework=Framework.keras.value,
            size_bytes=size,
            sha256=sha256,
            parameters=facts.parameters,
            input_shape=facts.input_shape,
            output_shape=facts.output_shape,
            keras_version=facts.keras_version,
            starred=False,
            created_at=_now(),
        )
        self._store.add(model)
        await self._store.flush()
        await self._storage.save(incoming, user_id, model.id)
        try:
            await self._store.commit()
        except BaseException:
            await self._storage.delete(user_id, model.id)
            raise
        return model

    async def _free_name(self, user_id: str, name: str) -> str:
        """`name`, or with the first number that makes it one the user does not have yet."""
        number = 1
        while await self._store.name_taken(user_id, candidate := numbered(name, number)):
            number += 1
        return candidate

    async def update(self, user_id: str, model_id: str, update: ModelUpdate) -> ModelOut:
        """Renames the user's model (its extension stays) or stars or unstars it; what
        `update` leaves out stays.

        Raises:
            ModelNotFound: The user has no model with the ID.
            ModelNameTaken: Another model of the user has the new name, in any case.
        """
        await self._store.lock_user(user_id)
        model = await self._store.model(user_id, model_id)
        if model is None:
            raise ModelNotFound
        if update.name is not None:
            name = update.name + _split(model.name)[1]
            if await self._store.name_taken(user_id, name, other_than=model.id):
                raise ModelNameTaken(name)
            model.name = name
        if update.starred is not None:
            model.starred = update.starred
        await self._store.commit()
        return _out(model)

    async def delete(self, user_id: str, model_id: str) -> None:
        """Deletes the user's model, then its file; a file that cannot be removed stays as an
        orphan (a warning), the model is gone.

        Raises:
            ModelNotFound: The user has no model with the ID.
        """
        if not await self._store.delete(user_id, model_id):
            raise ModelNotFound
        await self._store.commit()
        logger.info("User %s deleted model %s", user_id, model_id)
        try:
            await self._storage.delete(user_id, model_id)
        except OSError as error:
            logger.warning(
                "The file of the deleted model %s was not removed (%s)",
                model_id,
                type(error).__name__,
            )


class ModelsAccountDeletion:
    """Deletes a user's models with their account (an ``AccountDeletionHook``): the rows in the
    deletion's transaction, the files once it is committed."""

    def __init__(self, storage: ModelStorage) -> None:
        self._storage = storage

    async def __call__(self, user_id: str, db: AsyncSession, /) -> AfterDeletion:
        await ModelStore(db).delete_all(user_id)
        return partial(self._storage.delete_user, user_id)
