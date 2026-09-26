from datetime import UTC, datetime

import polars as pl

from candlestack.data import CANDLE_SCHEMA, Session, Timeframe
from candlestack.data.cache import decode_chunk, encode_chunk
from candlestack.data.service import bin_open, newest_minute


def utc(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=UTC).timestamp())


def test_newest_minute_around_the_clock() -> None:
    assert newest_minute(utc("2026-09-26T12:34:56"), None) == utc("2026-09-26T12:33")
    assert newest_minute(utc("2026-09-26T12:34:00"), None) == utc("2026-09-26T12:33")


def test_newest_minute_of_stocks(sessions: list[Session]) -> None:
    # 2024-11-29 is an early close (14:30-18:00 UTC), 2024-12-02 a normal Monday.
    assert newest_minute(utc("2024-11-29T15:00:30"), sessions) == utc("2024-11-29T14:59")
    assert newest_minute(utc("2024-11-29T14:30:59"), sessions) == utc("2024-11-27T20:59")
    assert newest_minute(utc("2024-11-29T14:31:00"), sessions) == utc("2024-11-29T14:30")
    assert newest_minute(utc("2024-11-30T10:00"), sessions) == utc("2024-11-29T17:59")
    assert newest_minute(utc("2024-12-02T14:00"), sessions) == utc("2024-11-29T17:59")


def test_bin_open_of_fixed_bins() -> None:
    first = utc("2026-09-24T11:07")

    assert bin_open(first, Timeframe.M1, None) == first
    assert bin_open(first, Timeframe.H4, None) == utc("2026-09-24T08:00")
    assert bin_open(first, Timeframe.D1, None) == utc("2026-09-24")


def test_bin_open_of_session_bins(sessions: list[Session]) -> None:
    first = utc("2024-06-03T15:10")  # 11:10 EDT, the session opened 13:30 UTC

    assert bin_open(first, Timeframe.H1, sessions) == utc("2024-06-03T14:30")
    assert bin_open(first, Timeframe.H4, sessions) == utc("2024-06-03T13:30")
    assert bin_open(first, Timeframe.D1, sessions) == utc("2024-06-03T13:30")
    assert bin_open(utc("2024-06-03T21:00"), Timeframe.H1, sessions) == utc("2024-06-03T21:00")


def test_chunk_round_trip() -> None:
    frame = pl.DataFrame(
        [(60, 10.0, 12.0, 9.0, 11.0, 0.5), (120, 11.0, 11.0, 11.0, 11.0, 0.0)],
        schema=CANDLE_SCHEMA,
        orient="row",
    )

    decoded, complete_until = decode_chunk(encode_chunk(frame, 1790380620))

    assert decoded.equals(frame)
    assert decoded.schema == CANDLE_SCHEMA
    assert complete_until == 1790380620


def test_empty_chunk_round_trip() -> None:
    frame = pl.DataFrame(schema=CANDLE_SCHEMA)

    decoded, _ = decode_chunk(encode_chunk(frame, 0))

    assert decoded.schema == CANDLE_SCHEMA
    assert decoded.height == 0
