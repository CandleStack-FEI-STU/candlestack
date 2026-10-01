"""The entry point of ``candlestack-bt`` (``[project.scripts]`` in pyproject.toml)."""

import argparse
from collections.abc import Sequence

from candlestack.cli.run import add_arguments, run


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the command with ``argv`` (``sys.argv[1:]`` when None) and returns its exit code.

    Tests call it directly instead of starting a process.
    """
    parser = argparse.ArgumentParser(
        prog="candlestack-bt",
        description="Backtest a model's predictions on candles.",
    )
    commands = parser.add_subparsers(dest="command", title="commands")
    run_parser = commands.add_parser(
        "run",
        help="backtest one model on one stock from Parquet files",
        description="Backtest one model's predictions on the candles of one stock and write "
        "trades.parquet, series.parquet, stats.json and run.json to --out.",
    )
    add_arguments(run_parser)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return run(args, run_parser)
