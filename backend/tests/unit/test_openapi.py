from pathlib import Path

from candlestack.openapi import render

SNAPSHOT = Path(__file__).parents[3] / "docs" / "openapi.json"


def test_snapshot_is_current() -> None:
    """docs/openapi.json is the API contract: it must change with the code."""
    assert SNAPSHOT.read_text(encoding="utf-8") == render(), (
        "docs/openapi.json is stale. Regenerate it from backend/: "
        "uv run python -m candlestack.openapi > ../docs/openapi.json"
    )
