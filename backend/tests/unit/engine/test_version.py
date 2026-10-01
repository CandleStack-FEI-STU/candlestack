import re

from candlestack.engine import ENGINE_VERSION


def test_engine_version_is_major_minor_patch() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", ENGINE_VERSION)
