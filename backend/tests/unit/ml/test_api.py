"""The models routes up to where they would need Postgres; the flows with it are integration
tests (tests/integration/ml)."""

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from candlestack.accounts import User
from candlestack.accounts.dependencies import current_user
from candlestack.core import Settings
from candlestack.ml.api import _upload_problem
from candlestack.ml.errors import (
    AccountGone,
    ModelCheckFailed,
    ModelTooLarge,
    StorageFull,
    TooManyModels,
    UnsupportedModelFormat,
    UploadInProgress,
    UploadTimeout,
)
from candlestack.ml.schemas import ModelCheck

PROBLEMS = "https://candlestack.tech/problems/"
ORIGIN = {"Origin": "http://testserver"}
MB = 1024 * 1024
USER = User(
    id="usr_7f3k2m9qx4",
    display_name="Ada",
    email="ada@example.com",
    created_at=datetime(2026, 10, 1, tzinfo=UTC),
    last_sign_in_at=datetime(2026, 10, 1, tzinfo=UTC),
)


@pytest.fixture
def signed_in(app: FastAPI) -> FastAPI:
    app.dependency_overrides[current_user] = lambda: USER
    return app


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/models"),
        ("POST", "/api/v1/models?name=lstm.keras"),
        ("PATCH", "/api/v1/models/mdl_7f3k2m9qx4"),
        ("DELETE", "/api/v1/models/mdl_7f3k2m9qx4"),
    ],
)
def test_the_models_need_a_session(client: TestClient, method: str, path: str) -> None:
    json = {"starred": True} if method == "PATCH" else None

    response = client.request(method, path, headers=ORIGIN, json=json)

    assert response.status_code == 401
    assert response.json()["type"] == PROBLEMS + "not-signed-in"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/v1/models?name=lstm.keras"),
        ("PATCH", "/api/v1/models/mdl_7f3k2m9qx4"),
        ("DELETE", "/api/v1/models/mdl_7f3k2m9qx4"),
    ],
)
@pytest.mark.usefixtures("signed_in")
def test_changes_need_the_apps_own_origin(client: TestClient, method: str, path: str) -> None:
    json = {"starred": True} if method == "PATCH" else None

    response = client.request(method, path, headers={"Origin": "https://evil.example"}, json=json)

    assert response.status_code == 403
    assert response.json()["type"] == PROBLEMS + "cross-origin-request"


@pytest.mark.parametrize("name", ["model.pt", "weights.h5", "model.onnx", "lstm.keras.zip"])
@pytest.mark.usefixtures("signed_in")
def test_other_formats_are_coming_soon(client: TestClient, name: str) -> None:
    response = client.post("/api/v1/models", params={"name": name}, content=b"x", headers=ORIGIN)

    assert response.status_code == 415
    assert response.json() == {
        "type": PROBLEMS + "unsupported-model-format",
        "title": "Unsupported model format",
        "status": 415,
        "detail": "Support for this format is coming soon. For now CandleStack takes Keras "
        "models (.keras).",
    }


@pytest.mark.usefixtures("signed_in")
def test_a_file_announced_larger_than_50_mb_is_refused_at_once(client: TestClient) -> None:
    response = client.post(
        "/api/v1/models",
        params={"name": "lstm.keras"},
        content=b"x",
        headers={**ORIGIN, "Content-Length": str(50 * MB + 1)},
    )

    assert response.status_code == 413
    assert response.json() == {
        "type": PROBLEMS + "model-too-large",
        "title": "Model too large",
        "status": 413,
        "detail": "The file is larger than 50 MB, the largest file an upload takes. Upload a "
        "smaller model.",
    }


@pytest.mark.parametrize(
    "params", [{}, {"name": ""}, {"name": "a" * 250 + ".keras"}], ids=["none", "empty", "long"]
)
@pytest.mark.usefixtures("signed_in")
def test_an_upload_needs_a_file_name(client: TestClient, params: dict[str, str]) -> None:
    response = client.post("/api/v1/models", params=params, content=b"x", headers=ORIGIN)

    assert response.status_code == 422
    assert response.json()["type"] == PROBLEMS + "validation"


@pytest.mark.usefixtures("signed_in")
def test_a_rename_is_validated(client: TestClient) -> None:
    response = client.patch("/api/v1/models/mdl_7f3k2m9qx4", json={"name": "a/b"}, headers=ORIGIN)

    assert response.status_code == 422
    assert response.json()["type"] == PROBLEMS + "validation"


def test_the_app_starts_with_its_model_storage(settings: Settings, client: TestClient) -> None:
    assert settings.model_storage_dir.is_dir()
    assert (settings.model_storage_dir / ".incoming").is_dir()


def test_the_default_model_storage_is_relative() -> None:
    assert Settings().model_storage_dir == Path("var/models")


@pytest.mark.parametrize(
    ("error", "status", "slug"),
    [
        (UnsupportedModelFormat(), 415, "unsupported-model-format"),
        (ModelTooLarge(), 413, "model-too-large"),
        (StorageFull(10, 20), 409, "storage-full"),
        (TooManyModels(), 409, "too-many-models"),
        (UploadInProgress(), 409, "upload-in-progress"),
        (UploadTimeout(), 408, "upload-timeout"),
        (ModelCheckFailed(ModelCheck.weights, "No weights."), 422, "model-check-failed"),
        (AccountGone(), 401, "not-signed-in"),
    ],
)
def test_each_refused_upload_has_its_problem_and_is_logged_by_ids(
    error: Exception, status: int, slug: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        problem = _upload_problem("usr_7f3k2m9qx4", error)

    assert (problem.status, problem.slug) == (status, slug)
    assert ";" not in problem.detail
    assert f"An upload of user usr_7f3k2m9qx4 was refused ({slug}" in caplog.text


def test_the_timeout_problem_names_the_minutes() -> None:
    assert _upload_problem("usr_7f3k2m9qx4", UploadTimeout()).detail == (
        "The file did not arrive within 2 minutes. Check the connection and upload it again."
    )
