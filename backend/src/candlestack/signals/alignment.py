"""Predictions next to their candles: time labels and alignment on ``ts``."""

from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True, slots=True)
class AlignReport:
    """What ``align`` could not match one to one.

    Attributes:
        predictions_without_candle: predictions whose ``ts`` has no candle; strict mode refuses
            them, otherwise they are dropped.
        candles_without_prediction: candles inside the aligned rows without a prediction of
            their own (the gaps); strict mode refuses them, otherwise they repeat the previous
            prediction.
    """

    predictions_without_candle: int
    candles_without_prediction: int


def relabel(frame: pl.DataFrame, timeframe_seconds: int, column: str = "ts") -> pl.DataFrame:
    """Turns close-time labels into open-time labels: ``column`` minus one timeframe, as Int64.

    The supervisor labels candles and predictions by the candle's close (the first 30m candle
    of a New York session is 10:00); the engine and ``align`` expect its open (09:30).

    Raises:
        ValueError: ``column`` is missing, not integer epoch seconds or has a missing value, or
            ``timeframe_seconds`` is not a positive int.
    """
    _check_ts(frame, column, "frame")
    if isinstance(timeframe_seconds, bool) or not isinstance(timeframe_seconds, int):
        raise ValueError(f"timeframe_seconds must be an int, got {timeframe_seconds!r}")
    if timeframe_seconds <= 0:
        raise ValueError(f"timeframe_seconds must be positive, got {timeframe_seconds}")
    return frame.with_columns(pl.col(column).cast(pl.Int64) - timeframe_seconds)


def align(
    candles: pl.DataFrame,
    predictions: pl.DataFrame,
    *,
    model: str | None = None,
    strict: bool = True,
) -> tuple[pl.DataFrame, AlignReport]:
    """The candles from the model's first to its last prediction, each with its ``prediction``.

    Joins on ``ts``, which labels the candle's open on both sides (see ``relabel``). A missing
    (null) prediction counts as no prediction, and missing candles are never filled in.

    Strict mode refuses both kinds of mismatch. Without it, a prediction whose ``ts`` has no
    candle is dropped, and a candle without a prediction of its own (a gap) repeats the previous
    one: the model said nothing new, so no new order follows, but the candle stays for the stop
    loss and the equity. The report counts both.

    Args:
        candles: ``ts`` and the other columns of the candles, which are kept; no
            ``prediction``.
        predictions: ``ts`` and ``prediction``, and ``model`` when the frame holds several
            models.
        model: aligns only this model's predictions.
        strict: refuses a prediction whose ``ts`` has no candle (wrong labels or missing
            candles) and a candle inside the rows without a prediction (a gap).

    Returns:
        The candle columns and ``prediction``, sorted by ``ts``, and what could not be matched.

    Raises:
        ValueError: a column is missing, the candles already have ``prediction``, ``ts`` is not
            integer epoch seconds or repeats, the predictions hold several models and ``model``
            is not given, no prediction is left to align, or (strict) a prediction has no candle
            or a candle has no prediction.
    """
    if "prediction" in candles.columns:
        raise ValueError("The candles already have a 'prediction' column: drop it first")
    candles = _unique_ts(candles, "candles")
    own = _unique_ts(_model_predictions(predictions, model), "predictions")
    landed = own.join(candles.select("ts"), on="ts", how="semi")
    without_candle = own.height - landed.height
    if strict and without_candle:
        first = own.join(candles.select("ts"), on="ts", how="anti")["ts"].min()
        has = "prediction has" if without_candle == 1 else "predictions have"
        raise ValueError(
            f"{without_candle} {has} no candle, first at ts {first}: check that both are "
            "labelled by the candle's open (relabel), or pass strict=False to drop them"
        )
    if landed.is_empty():
        raise ValueError("No prediction has a candle: check that both use the same labels")
    rows = (
        candles.filter(pl.col("ts").is_between(landed["ts"].min(), landed["ts"].max()))
        .join(landed, on="ts", how="left")
        .sort("ts")
    )
    gaps = rows["prediction"].null_count()
    if strict and gaps:
        first = rows.filter(pl.col("prediction").is_null())["ts"].min()
        has = "candle has" if gaps == 1 else "candles have"
        raise ValueError(
            f"{gaps} {has} no prediction, first at ts {first}: pass strict=False to repeat the "
            "previous prediction on them"
        )
    report = AlignReport(without_candle, gaps)
    return rows.with_columns(pl.col("prediction").forward_fill()), report


def _model_predictions(predictions: pl.DataFrame, model: str | None) -> pl.DataFrame:
    """``ts`` and ``prediction`` of one model, without missing predictions."""
    _require(predictions, ["ts", "prediction"], "predictions")
    if model is not None:
        _require(predictions, ["model"], "predictions")
        predictions = predictions.filter(pl.col("model") == model)
    elif "model" in predictions.columns and predictions["model"].n_unique() > 1:
        models = predictions["model"].n_unique()
        raise ValueError(f"The predictions hold {models} models: pass model= to pick one")
    own = predictions.select("ts", "prediction").drop_nulls("prediction")
    if own.is_empty():
        of = "" if model is None else f" of model {model!r}"
        raise ValueError(f"There are no predictions{of} to align")
    return own


def _unique_ts(frame: pl.DataFrame, what: str) -> pl.DataFrame:
    """The frame sorted by ``ts`` as Int64; raises ``ValueError`` when a ``ts`` repeats."""
    _check_ts(frame, "ts", what)
    frame = frame.with_columns(pl.col("ts").cast(pl.Int64)).sort("ts")
    repeated = frame.filter(pl.col("ts").is_duplicated())["ts"]
    if repeated.len():
        raise ValueError(f"The {what} repeat ts {repeated[0]}: each ts must be unique")
    return frame


def _check_ts(frame: pl.DataFrame, column: str, what: str) -> None:
    """Raises ``ValueError`` unless ``column`` holds integer epoch seconds, none missing."""
    _require(frame, [column], what)
    dtype = frame.schema[column]
    if not dtype.is_integer():
        raise ValueError(f"{column!r} of the {what} must be integer epoch seconds, not {dtype}")
    if frame[column].null_count():
        raise ValueError(f"{column!r} of the {what} has a missing value")


def _require(frame: pl.DataFrame, columns: list[str], what: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing column {', '.join(map(repr, missing))} in the {what}")
