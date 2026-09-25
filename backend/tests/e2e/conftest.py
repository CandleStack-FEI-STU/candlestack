"""Runs the e2e tests against the built image over HTTP.

With ``E2E_BASE_URL`` set, the tests use that running stack (CI starts it). Otherwise this
fixture builds and starts ``compose.yaml`` on ``127.0.0.1:$E2E_PORT`` (default 18000) and
removes it afterwards: ``E2E_PORT=18001 uv run pytest -m e2e`` from ``backend/``.
"""

import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).parent


@pytest.fixture(scope="session")
def base_url() -> Iterator[str]:
    if url := os.environ.get("E2E_BASE_URL"):
        yield url.rstrip("/")
        return

    port = os.environ.get("E2E_PORT", "18000")
    # Relative paths, cwd and WSLENV: also works with a docker CLI that wraps docker in WSL.
    compose = [shutil.which("docker") or "docker", "compose", "-f", "compose.yaml"]
    env = {**os.environ, "E2E_PORT": port, "WSLENV": f"E2E_PORT/u:{os.environ.get('WSLENV', '')}"}
    subprocess.run([*compose, "up", "-d", "--build", "--wait"], cwd=HERE, env=env, check=True)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        subprocess.run([*compose, "down", "--volumes"], cwd=HERE, env=env, check=True)


@pytest.fixture
def http(base_url: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=base_url, timeout=10) as client:
        yield client
