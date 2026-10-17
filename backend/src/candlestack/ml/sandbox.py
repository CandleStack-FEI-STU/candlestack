"""Runs the check of an uploaded file (``inspect.py``) in a short-lived child process, one at a
time, with a time limit; on Linux the child limits its own memory, CPU time and file size.

The check parses a file the user made with zipfile, json and h5py (the HDF5 C library): a
crafted file that crashes the parser or exhausts its memory then takes down only the child,
and fails the check instead of the API. The API process never imports h5py.
"""

import json
import logging
import os
import sys
from pathlib import Path

import anyio

from candlestack.ml.errors import ModelCheckFailed
from candlestack.ml.inspect import ModelFacts
from candlestack.ml.schemas import FILE_MAX_BYTES, ModelCheck

logger = logging.getLogger(__name__)

# A real model is checked in well under a second (the child's start included).
CHECK_TIMEOUT = 20.0
# One check at a time: they never pile up, and never use the thread pool that the sync
# dependencies of the routes need.
_CHECKS = anyio.CapacityLimiter(1)
_SRC = Path(__file__).parents[2]
# The child imports the check without the package roots, whose imports (the app, the
# database) it does not need: empty packages stand in for them. ``-I`` keeps the environment
# and the script's directory off its path.
_CHILD = """\
import sys, types
for name in ("candlestack", "candlestack.ml"):
    package = types.ModuleType(name)
    package.__path__ = [sys.argv[1] + "/" + name.replace(".", "/")]
    sys.modules[name] = package
from candlestack.ml.inspect import main
sys.exit(main(sys.argv[2:]))
"""
# What the child gets of the environment: no keys or database URL of the app. One thread for
# the numeric libraries, which would reserve memory per core otherwise.
_ENVIRONMENT_KEPT = ("PATH", "SYSTEMROOT", "TMPDIR", "TEMP", "TMP")
_THREADS = {"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
_SAVE_AGAIN = 'Save the model again with model.save("model.keras") and upload that file.'
TOO_LONG = "The check took too long. The file may be damaged. " + _SAVE_AGAIN
STOPPED = "The check of the file stopped before it finished. The file may be damaged. " + (
    _SAVE_AGAIN
)


def _environment() -> dict[str, str]:
    kept = {name: os.environ[name] for name in _ENVIRONMENT_KEPT if name in os.environ}
    return {**kept, **_THREADS}


async def check_upload(path: Path, scratch: Path) -> ModelFacts:
    """Checks the uploaded file at `path` in a child process; the weights are unpacked to
    `scratch`, which the caller removes.

    Raises:
        ModelCheckFailed: A check failed, the child took too long or stopped (crashed, killed
            at a limit).
    """
    command = [
        sys.executable,
        "-I",
        "-c",
        _CHILD,
        str(_SRC),
        str(path),
        str(scratch),
        str(FILE_MAX_BYTES),
    ]
    async with _CHECKS:
        # Past the time limit the child is killed.
        with anyio.move_on_after(CHECK_TIMEOUT) as limit:
            done = await anyio.run_process(command, check=False, env=_environment())
    if limit.cancelled_caught:
        logger.warning("The check of an upload took longer than %s s", CHECK_TIMEOUT)
        raise ModelCheckFailed(ModelCheck.opens, TOO_LONG)
    return _result(done.returncode, done.stdout)


def _result(returncode: int, stdout: bytes) -> ModelFacts:
    """What the child found.

    Raises:
        ModelCheckFailed: A check failed, or the child wrote no result.
    """
    try:
        result = json.loads(stdout) if returncode == 0 else None
        if result is not None and "failed" in result:
            failed = result["failed"]
            raise ModelCheckFailed(ModelCheck(failed["check"]), str(failed["detail"]))
        if result is not None:
            return ModelFacts(**result["facts"])
    except (ValueError, KeyError, TypeError):  # no JSON, or not what the child writes
        pass
    logger.warning("The check of an upload stopped (exit code %s)", returncode)
    raise ModelCheckFailed(ModelCheck.opens, STOPPED)
