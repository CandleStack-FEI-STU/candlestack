"""Fixtures of the integration tests: a real Redis at REDIS_URL (CI starts one, locally the
Redis of compose.yaml).

Without REDIS_URL the tests use DB 15 of the local Redis, not the dev backend's DB 0: the data
tests flush their database before each test.
"""

import os

import pytest


@pytest.fixture
def redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/15")
