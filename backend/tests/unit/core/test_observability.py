import json
import logging
import time
from collections.abc import Iterator
from typing import Any, cast, override

import pytest
import sentry_sdk
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport
from sentry_sdk.types import Log

from candlestack.core import ProblemError, Settings, setup_sentry
from candlestack.core.logging import request_id_var
from candlestack.core.observability import (
    ErrorBudget,
    _before_send_log,
    _traces_sampler,
)
from candlestack.main import create_app

logger = logging.getLogger("candlestack.test")


class CapturingTransport(Transport):
    """Keeps what the SDK would send to Sentry, so nothing leaves the test."""

    def __init__(self) -> None:
        super().__init__()
        self.envelopes: list[Envelope] = []

    @override
    def capture_envelope(self, envelope: Envelope) -> None:
        self.envelopes.append(envelope)

    def items(self, kind: str) -> list[dict[str, Any]]:
        sentry_sdk.flush()
        return [
            item.payload.json
            for envelope in self.envelopes
            for item in envelope.items
            if item.type == kind and item.payload.json is not None
        ]

    def logs(self) -> list[dict[str, Any]]:
        return [log for batch in self.items("log") for log in batch["items"]]


@pytest.fixture
def sentry(monkeypatch: pytest.MonkeyPatch) -> Iterator[CapturingTransport]:
    transport = CapturingTransport()
    init = sentry_sdk.init
    monkeypatch.setattr(sentry_sdk, "init", lambda **options: init(transport=transport, **options))
    yield transport
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        app_version="1.2.3",
        app_commit="abc1234",
        sentry_dsn="https://public@o1.ingest.de.sentry.io/1",
    )


@pytest.fixture
def app(sentry: CapturingTransport, app: FastAPI) -> FastAPI:
    @app.get("/api/test/crash")
    async def crash() -> None:
        headers = {"APCA-API-KEY-ID": "PKTESTKEY", "APCA-API-SECRET-KEY": "s3cr3t-value"}
        raise RuntimeError(f"upstream failed with {len(headers)} headers")

    @app.get("/api/test/problem")
    async def problem() -> None:
        raise ProblemError(502, "source-unavailable", "Source unavailable", "Binance is down.")

    @app.get("/api/test/warning")
    async def warning() -> dict[str, bool]:
        logger.warning("Binance answered slowly")
        return {"ok": True}

    @app.get("/api/test/logged-error")
    async def logged_error() -> dict[str, bool]:
        logger.error("Invalid data from %s", "binance")
        return {"ok": True}

    return app


def test_no_dsn_starts_nothing() -> None:
    assert setup_sentry(Settings(app_env="test")) is False
    assert not sentry_sdk.get_client().is_active()


def test_an_unhandled_error_is_one_event(sentry: CapturingTransport, client: TestClient) -> None:
    response = client.get("/api/test/crash", headers={"CF-Ray": "8c1f0e2d-VIE"})

    assert response.status_code == 500
    [event] = sentry.items("event")
    assert event["exception"]["values"][-1]["type"] == "RuntimeError"
    assert event["environment"] == "test"
    assert event["release"] == "1.2.3"
    assert event["tags"]["request_id"] == "8c1f0e2d-VIE" == response.headers["x-request-id"]


def test_secrets_and_personal_data_are_not_sent(
    sentry: CapturingTransport, client: TestClient
) -> None:
    client.get(
        "/api/test/crash",
        headers={
            "CF-Connecting-IP": "203.0.113.7",
            "Cf-Access-Authenticated-User-Email": "someone@example.com",
            "Cookie": "CF_Authorization=zq9-session",
        },
    )

    [event] = sentry.items("event")
    frame = event["exception"]["values"][-1]["stacktrace"]["frames"][-1]
    assert frame["vars"]["headers"] == {
        "APCA-API-KEY-ID": "[Filtered]",
        "APCA-API-SECRET-KEY": "[Filtered]",
    }
    # The source lines around each frame are sent as they are, and here they hold the test's
    # own literals; everything else must not.
    for each in event["exception"]["values"]:
        for code in each["stacktrace"]["frames"]:
            for key in ("pre_context", "context_line", "post_context"):
                code.pop(key, None)
    sent = json.dumps(event)
    for value in ("PKTESTKEY", "s3cr3t-value", "203.0.113.7", "someone@example.com", "zq9-session"):
        assert value not in sent


@pytest.mark.parametrize("path", ["/api/test/problem", "/api/test/warning", "/api/nothing-here"])
def test_problems_and_warnings_are_not_errors(
    sentry: CapturingTransport, client: TestClient, path: str
) -> None:
    client.get(path)

    assert sentry.items("event") == []


def test_a_logged_error_is_an_event(sentry: CapturingTransport, client: TestClient) -> None:
    client.get("/api/test/logged-error")

    [event] = sentry.items("event")
    assert event["logentry"]["message"] == "Invalid data from %s"
    assert event["tags"]["request_id"]


def test_logs_carry_the_request_id(sentry: CapturingTransport, client: TestClient) -> None:
    response = client.get("/api/test/warning")

    [warning] = [log for log in sentry.logs() if log["body"] == "Binance answered slowly"]
    assert warning["level"] == "warn"
    assert warning["attributes"]["request_id"]["value"] == response.headers["x-request-id"]


def test_health_checks_are_neither_traced_nor_logged(
    sentry: CapturingTransport, client: TestClient
) -> None:
    client.get("/api/health")
    client.get("/api/test/warning")

    traced = [event["transaction"] for event in sentry.items("transaction")]
    logged = [log["attributes"].get("path", {}).get("value") for log in sentry.logs()]
    assert traced == ["/api/test/warning"]
    assert "/api/health" not in logged
    assert "/api/test/warning" in logged


def test_a_traced_request_is_profiled(sentry: CapturingTransport, client: TestClient) -> None:
    client.get("/api/test/warning")

    [transaction] = sentry.items("transaction")
    profiler_id = transaction["contexts"]["profile"]["profiler_id"]
    # The profiler stops once no traced request runs, and then sends what it sampled.
    deadline = time.monotonic() + 5
    while not (chunks := sentry.items("profile_chunk")) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert chunks
    assert {chunk["profiler_id"] for chunk in chunks} == {profiler_id}


def test_the_error_budget_drops_errors_over_it() -> None:
    now = [0.0]
    budget = ErrorBudget(2, 3600, clock=lambda: now[0])

    assert [budget.take() for _ in range(3)] == [True, True, False]
    now[0] = 3600.0
    assert budget.take() is True


def test_traces_sampler() -> None:
    sample = _traces_sampler(0.2)

    assert sample({"asgi_scope": {"path": "/api/v1/candles"}}) == 0.2
    assert sample({"asgi_scope": {"path": "/api/health"}}) == 0.0
    assert sample({"asgi_scope": {"path": "/api/health/sources"}}) == 0.0
    assert sample({"parent_sampled": True, "asgi_scope": {"path": "/api/health"}}) == 1.0
    assert sample({}) == 0.2


def test_before_send_log_outside_a_request() -> None:
    def log(**attributes: str) -> Log:
        return cast("Log", {"attributes": attributes})

    assert (
        _before_send_log(log(**{"logger.name": "candlestack.access", "path": "/api/health"}), {})
        is None
    )
    other = _before_send_log(log(**{"logger.name": "candlestack.data"}), {})
    assert other is not None
    assert "request_id" not in other["attributes"]
    token = request_id_var.set("8c1f0e2d")
    try:
        inside = _before_send_log(log(**{"logger.name": "candlestack.data"}), {})
    finally:
        request_id_var.reset(token)
    assert inside is not None
    assert inside["attributes"]["request_id"] == "8c1f0e2d"


@pytest.mark.parametrize(
    ("app_env", "status"), [("stage", 500), ("prod", 404), ("pr-12", 404), ("local", 404)]
)
def test_the_check_route_is_on_stage_only(app_env: str, status: int) -> None:
    with TestClient(create_app(Settings(app_env=app_env)), raise_server_exceptions=False) as client:
        assert client.get("/api/debug/sentry-error").status_code == status
