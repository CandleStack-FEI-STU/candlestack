"""Where the files of the uploaded models are kept: ``ModelStorage``, which the service uses,
and ``LocalModelStorage``, a directory (a Docker volume on the VM). Another storage, such as
Cloudflare R2, can replace it without touching the service.

An upload streams into a file of its own in the incoming directory, is checked there and then
moved to its place, so a model's file is always whole. The files are served only through the
API, never straight from the directory.
"""

import logging
import secrets
import shutil
import time
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Protocol

import anyio

logger = logging.getLogger(__name__)

# An incoming file older than this was left by an upload that crashed.
STALE_INCOMING = timedelta(hours=1)
_INCOMING = ".incoming"
_SUFFIX = ".keras"


class ModelStorage(Protocol):
    def incoming_path(self) -> Path:
        """A new local path for a file that comes in (an upload, the weights unpacked by the
        check); the caller removes it with `discard`."""
        ...

    async def save(self, incoming: Path, user_id: str, model_id: str) -> None:
        """Moves the finished file `incoming` to the place of the user's model."""
        ...

    async def delete(self, user_id: str, model_id: str) -> None:
        """Deletes the file of the user's model; nothing when it is gone already."""
        ...

    async def delete_user(self, user_id: str) -> None:
        """Deletes the files of every model of the user."""
        ...

    async def discard(self, incoming: Path) -> None:
        """Removes a file of `incoming_path`; nothing when there is none."""
        ...

    async def prepare(self) -> None:
        """Makes the storage ready at startup and removes what crashed uploads left there
        (incoming files older than an hour)."""
        ...


class LocalModelStorage:
    """The files in a directory: ``<user_id>/<model_id>.keras``, and the uploads in progress
    as ``.incoming/<random>.part``, on the same filesystem, so a move is an atomic rename."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._incoming = root / _INCOMING

    def path(self, user_id: str, model_id: str) -> Path:
        """Where the file of the user's model is."""
        return self._root / user_id / f"{model_id}{_SUFFIX}"

    def incoming_path(self) -> Path:
        return self._incoming / f"{secrets.token_hex(16)}.part"

    async def save(self, incoming: Path, user_id: str, model_id: str) -> None:
        target = self.path(user_id, model_id)

        def move() -> None:
            target.parent.mkdir(exist_ok=True)
            incoming.replace(target)

        await anyio.to_thread.run_sync(move)

    async def delete(self, user_id: str, model_id: str) -> None:
        await anyio.to_thread.run_sync(
            partial(self.path(user_id, model_id).unlink, missing_ok=True)
        )

    async def delete_user(self, user_id: str) -> None:
        def remove() -> None:
            # Gone already is fine: a user who never uploaded has no directory.
            if (directory := self._root / user_id).exists():
                shutil.rmtree(directory)

        await anyio.to_thread.run_sync(remove)

    async def discard(self, incoming: Path) -> None:
        await anyio.to_thread.run_sync(partial(incoming.unlink, missing_ok=True))

    async def prepare(self) -> None:
        removed = await anyio.to_thread.run_sync(self._prepare)
        if removed:
            logger.info("Removed %d incoming model files that crashed uploads left", removed)

    def _prepare(self) -> int:
        self._incoming.mkdir(parents=True, exist_ok=True)
        stale_before = time.time() - STALE_INCOMING.total_seconds()
        removed = 0
        for path in self._incoming.iterdir():
            if path.stat().st_mtime < stale_before:
                path.unlink(missing_ok=True)
                removed += 1
        return removed
