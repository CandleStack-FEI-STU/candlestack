"""The check of an upload in its child process: what it finds, and a child that takes too long,
crashes or writes something else fails the check instead of the request."""

import logging
from pathlib import Path

import pytest

from candlestack.ml import sandbox
from candlestack.ml.errors import ModelCheckFailed
from candlestack.ml.inspect import ModelFacts
from candlestack.ml.sandbox import STOPPED, TOO_LONG, check_upload
from candlestack.ml.schemas import ModelCheck

pytestmark = pytest.mark.anyio

FIXTURES = Path(__file__).parents[2] / "fixtures" / "keras"


@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    return tmp_path / "weights.part"


async def test_a_model_passes(scratch: Path) -> None:
    facts = await check_upload(FIXTURES / "functional.keras", scratch)

    assert facts == ModelFacts("3.15.1", 9325, [25, 23], [1])


async def test_a_failed_check_is_named(scratch: Path) -> None:
    with pytest.raises(ModelCheckFailed) as failed:
        await check_upload(FIXTURES / "lambda_layer.keras", scratch)

    assert failed.value.check is ModelCheck.opens
    assert failed.value.detail.startswith('The layer "lambda" uses custom code (Lambda)')


async def test_a_check_that_takes_too_long_is_killed(
    scratch: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(sandbox, "_CHILD", "import time; time.sleep(30)")
    monkeypatch.setattr(sandbox, "CHECK_TIMEOUT", 0.5)

    with caplog.at_level(logging.WARNING), pytest.raises(ModelCheckFailed) as failed:
        await check_upload(FIXTURES / "functional.keras", scratch)

    assert (failed.value.check, failed.value.detail) == (ModelCheck.opens, TOO_LONG)
    assert "The check of an upload took longer than 0.5 s" in caplog.text


@pytest.mark.parametrize(
    "child",
    [
        "import sys; sys.exit(3)",
        "print('not JSON')",
        "print('{\"other\": 1}')",
        'print(\'{"facts": {"parameters": 1}}\')',
        'print(\'{"failed": {"check": "loads", "detail": "x"}}\')',
    ],
    ids=["crash", "not-json", "unknown-result", "missing-facts", "unknown-check"],
)
async def test_a_child_without_a_result_fails_the_check(
    child: str, scratch: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(sandbox, "_CHILD", child)

    with caplog.at_level(logging.WARNING), pytest.raises(ModelCheckFailed) as failed:
        await check_upload(FIXTURES / "functional.keras", scratch)

    assert (failed.value.check, failed.value.detail) == (ModelCheck.opens, STOPPED)
    assert "The check of an upload stopped (exit code" in caplog.text


def test_the_child_gets_no_secrets_of_the_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://secret")
    monkeypatch.setenv("PATH", "/usr/bin")

    environment = sandbox._environment()

    assert "DATABASE_URL" not in environment
    assert environment["PATH"] == "/usr/bin"
    assert environment["OPENBLAS_NUM_THREADS"] == "1"
