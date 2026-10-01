"""The entry point of ``candlestack-bt`` (``[project.scripts]`` in pyproject.toml)."""

import argparse
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the command with ``argv`` (``sys.argv[1:]`` when None) and returns its exit code.

    Tests call it directly instead of starting a process.
    """
    parser = argparse.ArgumentParser(
        prog="candlestack-bt",
        description="Backtest a model's predictions on candles.",
    )
    parser.parse_args(argv)
    parser.print_help()
    return 0
