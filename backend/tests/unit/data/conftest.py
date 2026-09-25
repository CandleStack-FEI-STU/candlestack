"""Fixtures of the data module tests: the real NYSE calendar of 2024 as Alpaca returns it."""

import json
from pathlib import Path
from typing import Any

import pytest

from candlestack.data import Session, parse_calendar

FIXTURES = Path(__file__).parents[2] / "fixtures"


@pytest.fixture(scope="session")
def calendar_items() -> list[dict[str, Any]]:
    """``GET /v2/calendar`` for 2024: 252 days, early closes 07-03, 11-29 and 12-24."""
    return json.loads((FIXTURES / "alpaca" / "calendar-2024.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def sessions(calendar_items: list[dict[str, Any]]) -> list[Session]:
    return parse_calendar(calendar_items)
