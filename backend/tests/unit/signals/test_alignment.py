from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from candlestack.signals import AlignReport, align, relabel

HALF_HOUR = 1800
NEW_YORK = ZoneInfo("America/New_York")


def utc(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=UTC).timestamp())


def new_york(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=NEW_YORK).timestamp())


def candles(*ts: int) -> pl.DataFrame:
    """Candles that open at ``ts``; candle t opens at t and closes at t + 0.5."""
    return pl.DataFrame(
        {"ts": list(ts), "open": [float(t) for t in ts], "close": [t + 0.5 for t in ts]},
        schema={"ts": pl.Int64, "open": pl.Float64, "close": pl.Float64},
    )


def predictions(values: dict[int, float | None], model: str | None = None) -> pl.DataFrame:
    frame = pl.DataFrame(
        {"ts": list(values), "prediction": list(values.values())},
        schema={"ts": pl.Int64, "prediction": pl.Float64},
    )
    return frame if model is None else frame.with_columns(model=pl.lit(model))


def rows(frame: pl.DataFrame) -> list[tuple[int, float]]:
    return list(frame.select("ts", "prediction").iter_rows())


# relabel


def test_relabel_moves_the_supervisors_close_labels_to_open_times() -> None:
    # He labels a 30m candle by its close, so the first one of a session is 10:00 New York; it
    # opens at 09:30. The shift is one timeframe in winter (EST) and in summer (EDT) alike.
    frame = pl.DataFrame(
        {
            "ts": [
                new_york("2025-01-07T10:00"),
                new_york("2025-01-07T10:30"),
                new_york("2025-07-07T10:00"),
            ],
            "close": [1.0, 2.0, 3.0],
        }
    )

    result = relabel(frame, HALF_HOUR)

    assert result["ts"].to_list() == [
        utc("2025-01-07T14:30"),
        utc("2025-01-07T15:00"),
        utc("2025-07-07T13:30"),
    ]
    assert result["close"].to_list() == [1.0, 2.0, 3.0]


def test_relabel_shifts_only_the_named_column_and_makes_it_int64() -> None:
    frame = pl.DataFrame(
        {"unix": [3600, 5400], "ts": [7, 8]}, schema={"unix": pl.Int32, "ts": pl.Int64}
    )

    result = relabel(frame, HALF_HOUR, column="unix")

    assert result.schema == {"unix": pl.Int64, "ts": pl.Int64}
    assert result.rows() == [(1800, 7), (3600, 8)]


@pytest.mark.parametrize(
    ("frame", "timeframe", "message"),
    [
        (pl.DataFrame({"unix": [1800]}), HALF_HOUR, "Missing column 'ts' in the frame"),
        (
            pl.DataFrame({"ts": [1800.0]}),
            HALF_HOUR,
            "'ts' of the frame must be integer epoch seconds, not Float64",
        ),
        (
            pl.DataFrame({"ts": [datetime(2025, 1, 7, tzinfo=UTC)]}),
            HALF_HOUR,
            "'ts' of the frame must be integer epoch seconds, not Datetime",
        ),
        (pl.DataFrame({"ts": [1800, None]}), HALF_HOUR, "'ts' of the frame has a missing value"),
        (pl.DataFrame({"ts": [1800]}), 0, "timeframe_seconds must be positive, got 0"),
        (pl.DataFrame({"ts": [1800]}), -HALF_HOUR, "timeframe_seconds must be positive, got -1800"),
        (pl.DataFrame({"ts": [1800]}), 1800.0, "timeframe_seconds must be an int, got 1800.0"),
        (pl.DataFrame({"ts": [1800]}), 0.5, "timeframe_seconds must be an int, got 0.5"),
        (pl.DataFrame({"ts": [1800]}), True, "timeframe_seconds must be an int, got True"),
    ],
)
def test_relabel_rejects(frame: pl.DataFrame, timeframe: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        relabel(frame, timeframe)


# align


def test_align_keeps_the_candles_from_the_first_to_the_last_prediction() -> None:
    result, report = align(
        candles(100, 200, 300, 400, 500, 600),
        predictions({200: 0.2, 300: -0.3, 400: 0.0, 500: 0.5}),
    )

    assert result.rows() == [
        (200, 200.0, 200.5, 0.2),
        (300, 300.0, 300.5, -0.3),
        (400, 400.0, 400.5, 0.0),
        (500, 500.0, 500.5, 0.5),
    ]
    assert result.columns == ["ts", "open", "close", "prediction"]
    assert report == AlignReport(predictions_without_candle=0, candles_without_prediction=0)


def test_align_keeps_the_first_and_the_last_candle_when_they_have_predictions() -> None:
    result, _ = align(candles(100, 200, 300), predictions({100: 0.1, 200: 0.2, 300: 0.3}))

    assert rows(result) == [(100, 0.1), (200, 0.2), (300, 0.3)]


def test_align_repeats_the_previous_prediction_on_candles_without_one() -> None:
    result, report = align(
        candles(100, 200, 300, 400, 500),
        predictions({100: 0.1, 400: -0.4, 500: 0.5}),
        strict=False,
    )

    assert rows(result) == [(100, 0.1), (200, 0.1), (300, 0.1), (400, -0.4), (500, 0.5)]
    assert report == AlignReport(predictions_without_candle=0, candles_without_prediction=2)


def test_align_counts_a_missing_prediction_as_no_prediction() -> None:
    result, report = align(
        candles(100, 200, 300, 400),
        predictions({100: None, 200: 0.2, 300: None, 400: 0.4}),
        strict=False,
    )

    assert rows(result) == [(200, 0.2), (300, 0.2), (400, 0.4)]
    assert report == AlignReport(predictions_without_candle=0, candles_without_prediction=1)


def test_align_does_not_fill_in_missing_candles() -> None:
    # The candle at 300 is missing from the data: no row is made up for it.
    result, report = align(candles(100, 200, 400), predictions({100: 0.1, 400: 0.4}), strict=False)

    assert rows(result) == [(100, 0.1), (200, 0.1), (400, 0.4)]
    assert report == AlignReport(predictions_without_candle=0, candles_without_prediction=1)


def test_align_takes_the_rows_of_the_given_model() -> None:
    both = pl.concat(
        [
            predictions({100: 0.1, 200: 0.2, 300: 0.3, 400: 0.4, 500: 0.5}, "wide"),
            predictions({300: -0.3, 400: -0.4}, "narrow"),
        ]
    )

    result, report = align(candles(100, 200, 300, 400, 500), both, model="narrow")

    assert rows(result) == [(300, -0.3), (400, -0.4)]
    assert result.columns == ["ts", "open", "close", "prediction"]
    assert report == AlignReport(predictions_without_candle=0, candles_without_prediction=0)


def test_align_needs_no_model_name_for_a_single_model() -> None:
    result, _ = align(candles(100, 200), predictions({100: 0.1, 200: 0.2}, "only"))

    assert rows(result) == [(100, 0.1), (200, 0.2)]


def test_align_needs_the_model_name_when_the_predictions_hold_several() -> None:
    both = pl.concat([predictions({100: 0.1}, "a"), predictions({100: 0.2}, "b")])

    with pytest.raises(ValueError, match="The predictions hold 2 models: pass model= to pick one"):
        align(candles(100), both)


@pytest.mark.parametrize(
    "ts",
    [
        pytest.param(50, id="before the first candle"),
        pytest.param(250, id="between two candles"),
        pytest.param(300, id="on a missing candle"),
        pytest.param(700, id="after the last candle"),
    ],
)
def test_align_strict_refuses_a_prediction_without_a_candle(ts: int) -> None:
    with pytest.raises(ValueError, match=f"1 prediction has no candle, first at ts {ts}: "):
        align(candles(100, 200, 400, 500), predictions({100: 0.1, ts: 0.9, 400: 0.4}))


def test_align_strict_names_the_first_of_several_predictions_without_a_candle() -> None:
    with pytest.raises(ValueError, match="2 predictions have no candle, first at ts 50: "):
        align(candles(100, 200), predictions({250: 0.2, 50: 0.1, 100: 0.0}))


@pytest.mark.parametrize(
    ("values", "ts"),
    [
        pytest.param({100: 0.1, 300: 0.3}, 200, id="no prediction"),
        pytest.param({100: 0.1, 200: None, 300: 0.3}, 200, id="missing prediction"),
    ],
)
def test_align_strict_refuses_a_candle_without_a_prediction(
    values: dict[int, float | None], ts: int
) -> None:
    with pytest.raises(ValueError, match=f"1 candle has no prediction, first at ts {ts}: "):
        align(candles(100, 200, 300), predictions(values))


def test_align_strict_names_the_first_of_several_candles_without_a_prediction() -> None:
    with pytest.raises(ValueError, match="2 candles have no prediction, first at ts 200: "):
        align(candles(100, 200, 300, 400, 500), predictions({100: 0.1, 300: 0.3, 500: 0.5}))


def test_align_strict_refuses_a_prediction_without_a_candle_before_a_gap() -> None:
    # 200 has no prediction and 250 has no candle: the prediction is reported first.
    with pytest.raises(ValueError, match="1 prediction has no candle, first at ts 250: "):
        align(candles(100, 200, 300), predictions({100: 0.1, 250: 0.2, 300: 0.3}))


def test_align_strict_takes_a_missing_candle_without_a_prediction() -> None:
    # The candle at 300 is missing and so is its prediction: no gap among the rows that exist.
    result, report = align(candles(100, 200, 400), predictions({100: 0.1, 200: 0.2, 400: 0.4}))

    assert rows(result) == [(100, 0.1), (200, 0.2), (400, 0.4)]
    assert report == AlignReport(predictions_without_candle=0, candles_without_prediction=0)


def test_align_non_strict_drops_predictions_without_a_candle_and_counts_them() -> None:
    # One prediction before the first candle and one on the missing candle 300: the rows start
    # at the first prediction that has a candle, and 400 repeats the one of 200.
    result, report = align(
        candles(100, 200, 400, 500, 600),
        predictions({50: 0.05, 200: 0.2, 300: 0.3, 500: 0.5}),
        strict=False,
    )

    assert rows(result) == [(200, 0.2), (400, 0.2), (500, 0.5)]
    assert report == AlignReport(predictions_without_candle=2, candles_without_prediction=1)


def test_align_non_strict_refuses_when_no_prediction_has_a_candle() -> None:
    with pytest.raises(ValueError, match="No prediction has a candle"):
        align(candles(100, 200), predictions({150: 0.1}), strict=False)


def test_align_sorts_by_ts_and_makes_it_int64() -> None:
    unsorted = candles(300, 100, 200).with_columns(pl.col("ts").cast(pl.Int32))
    later_first = predictions({300: 0.3, 100: 0.1}).with_columns(pl.col("ts").cast(pl.UInt32))

    result, _ = align(unsorted, later_first, strict=False)

    assert rows(result) == [(100, 0.1), (200, 0.1), (300, 0.3)]
    assert result.schema["ts"] == pl.Int64


def test_align_keeps_float32_predictions_as_they_are() -> None:
    float32 = predictions({100: 0.7}).with_columns(pl.col("prediction").cast(pl.Float32))

    result, _ = align(candles(100), float32)

    assert result.schema["prediction"] == pl.Float32
    assert result["prediction"].to_list() == float32["prediction"].to_list()


@pytest.mark.parametrize(
    ("candle_frame", "prediction_frame", "options", "message"),
    [
        pytest.param(
            candles(100, 200, 200),
            predictions({100: 0.1}),
            {},
            "The candles repeat ts 200: each ts must be unique",
            id="repeated candle",
        ),
        pytest.param(
            candles(100, 200),
            pl.concat([predictions({200: 0.1}), predictions({200: 0.2})]),
            {},
            "The predictions repeat ts 200: each ts must be unique",
            id="repeated prediction",
        ),
        pytest.param(
            candles(100, 200),
            pl.concat([predictions({100: 0.1}, "a"), predictions({100: 0.2}, "a")]),
            {"model": "a"},
            "The predictions repeat ts 100: each ts must be unique",
            id="repeated prediction of the model",
        ),
        pytest.param(
            candles(100),
            predictions({100: 0.1}, "a"),
            {"model": "b"},
            "There are no predictions of model 'b' to align",
            id="unknown model",
        ),
        pytest.param(
            candles(100),
            predictions({100: None}),
            {},
            "There are no predictions to align",
            id="only missing predictions",
        ),
        pytest.param(
            candles(100),
            predictions({100: 0.1}),
            {"model": "a"},
            "Missing column 'model' in the predictions",
            id="model without a model column",
        ),
        pytest.param(
            pl.DataFrame({"open": [1.0]}),
            predictions({100: 0.1}),
            {},
            "Missing column 'ts' in the candles",
            id="candles without ts",
        ),
        pytest.param(
            candles(100).with_columns(prediction=pl.lit(9.0)),
            predictions({100: 0.1}),
            {},
            "The candles already have a 'prediction' column: drop it first",
            id="candles with a prediction",
        ),
        pytest.param(
            candles(100),
            pl.DataFrame({"unix": [100], "value": [0.1]}),
            {},
            "Missing column 'ts', 'prediction' in the predictions",
            id="predictions without ts and prediction",
        ),
        pytest.param(
            candles(100).with_columns(pl.col("ts").cast(pl.Float64)),
            predictions({100: 0.1}),
            {},
            "'ts' of the candles must be integer epoch seconds, not Float64",
            id="float candle ts",
        ),
        pytest.param(
            candles(100),
            pl.DataFrame({"ts": [100, None], "prediction": [0.1, 0.2]}),
            {},
            "'ts' of the predictions has a missing value",
            id="missing prediction ts",
        ),
    ],
)
def test_align_rejects(
    candle_frame: pl.DataFrame,
    prediction_frame: pl.DataFrame,
    options: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        align(candle_frame, prediction_frame, **options)


def test_relabelled_supervisor_files_align_on_open_times() -> None:
    # Both of his files are labelled by the candle's close; relabelled, they meet on the opens.
    closes = [
        new_york("2025-01-07T10:00"),
        new_york("2025-01-07T10:30"),
        new_york("2025-01-07T11:00"),
    ]
    his_candles = pl.DataFrame({"ts": closes, "close": [1.0, 2.0, 3.0]})
    his_predictions = pl.DataFrame({"ts": closes[1:], "prediction": [0.2, 0.3]})

    result, report = align(relabel(his_candles, HALF_HOUR), relabel(his_predictions, HALF_HOUR))

    assert result.rows() == [
        (new_york("2025-01-07T10:00"), 2.0, 0.2),
        (new_york("2025-01-07T10:30"), 3.0, 0.3),
    ]
    assert report == AlignReport(predictions_without_candle=0, candles_without_prediction=0)
