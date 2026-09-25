from datetime import UTC, date, datetime

import pytest

from candlestack.data import (
    DataIntegrityError,
    Session,
    Timeframe,
    parse_calendar,
    session_bins,
    sessions_between,
)

HOUR = 3600


def utc(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=UTC).timestamp())


def by_date(sessions: list[Session], day: str) -> Session:
    return next(session for session in sessions if session.date == date.fromisoformat(day))


def test_parse_calendar_reads_every_trading_day(sessions: list[Session]) -> None:
    assert len(sessions) == 252
    assert sessions[0] == Session(
        date(2024, 1, 2), utc("2024-01-02 14:30"), utc("2024-01-02 21:00")
    )
    assert sessions == sorted(sessions, key=lambda session: session.date)


@pytest.mark.parametrize(
    ("day", "open_utc", "close_utc"),
    [
        # DST starts on Sunday 2024-03-10: the open moves from 14:30 to 13:30 UTC
        ("2024-03-08", "2024-03-08 14:30", "2024-03-08 21:00"),
        ("2024-03-11", "2024-03-11 13:30", "2024-03-11 20:00"),
        # DST ends on Sunday 2024-11-03
        ("2024-11-01", "2024-11-01 13:30", "2024-11-01 20:00"),
        ("2024-11-04", "2024-11-04 14:30", "2024-11-04 21:00"),
        # early closes at 13:00 New York time
        ("2024-07-03", "2024-07-03 13:30", "2024-07-03 17:00"),
        ("2024-11-29", "2024-11-29 14:30", "2024-11-29 18:00"),
        ("2024-12-24", "2024-12-24 14:30", "2024-12-24 18:00"),
    ],
)
def test_parse_calendar_converts_new_york_time(
    sessions: list[Session], day: str, open_utc: str, close_utc: str
) -> None:
    session = by_date(sessions, day)

    assert (session.open, session.close) == (utc(open_utc), utc(close_utc))


def test_holiday_has_no_session(sessions: list[Session]) -> None:
    days = sessions_between(sessions, utc("2024-07-03 00:00"), utc("2024-07-06 00:00"))

    assert [session.date for session in days] == [date(2024, 7, 3), date(2024, 7, 5)]


def test_parse_calendar_sorts_by_date() -> None:
    items = [
        {"date": "2024-06-04", "open": "09:30", "close": "16:00"},
        {"date": "2024-06-03", "open": "09:30", "close": "16:00"},
    ]

    assert [session.date for session in parse_calendar(items)] == [
        date(2024, 6, 3),
        date(2024, 6, 4),
    ]


@pytest.mark.parametrize(
    "item",
    [
        {"date": "2024-06-03", "open": "09:30"},
        {"date": "2024-06-03", "open": "9.30", "close": "16:00"},
        {"date": "06/03/2024", "open": "09:30", "close": "16:00"},
        {"date": "2024-06-03", "open": "16:00", "close": "09:30"},
        {"date": 20240603, "open": "09:30", "close": "16:00"},
    ],
)
def test_parse_calendar_rejects_malformed_days(item: dict[str, object]) -> None:
    with pytest.raises(DataIntegrityError, match="calendar"):
        parse_calendar([item])


def test_sessions_between_overlap_rules(sessions: list[Session]) -> None:
    monday = by_date(sessions, "2024-06-03")
    tuesday = by_date(sessions, "2024-06-04")

    def dates(start: int, end: int) -> list[date]:
        return [session.date for session in sessions_between(sessions, start, end)]

    # a period inside one session, and one that ends exactly at the next open
    assert dates(monday.open + HOUR, monday.open + 2 * HOUR) == [monday.date]
    assert dates(monday.open, tuesday.open) == [monday.date]
    # a session that closes exactly at start is not included
    assert dates(monday.close, tuesday.close) == [tuesday.date]
    # nights and weekends
    assert dates(monday.close, tuesday.open) == []
    assert dates(utc("2024-06-01 00:00"), utc("2024-06-03 00:00")) == []
    assert len(sessions_between(sessions, utc("2024-01-01 00:00"), utc("2025-01-01 00:00"))) == 252


@pytest.mark.parametrize(
    ("timeframe", "normal", "early_close"),
    [
        (Timeframe.M1, 390, 210),
        (Timeframe.M5, 78, 42),
        (Timeframe.M15, 26, 14),
        (Timeframe.H1, 7, 4),
        (Timeframe.H4, 2, 1),
        (Timeframe.D1, 1, 1),
    ],
)
def test_session_bin_counts(
    sessions: list[Session], timeframe: Timeframe, normal: int, early_close: int
) -> None:
    assert len(session_bins(by_date(sessions, "2024-06-03"), timeframe)) == normal
    assert len(session_bins(by_date(sessions, "2024-11-29"), timeframe)) == early_close


def test_session_bins_on_a_normal_day(sessions: list[Session]) -> None:
    session = by_date(sessions, "2024-06-03")  # 09:30-16:00 EDT = 13:30-20:00 UTC

    assert session_bins(session, Timeframe.H1) == [
        (utc("2024-06-03 13:30"), utc("2024-06-03 14:30")),
        (utc("2024-06-03 14:30"), utc("2024-06-03 15:30")),
        (utc("2024-06-03 15:30"), utc("2024-06-03 16:30")),
        (utc("2024-06-03 16:30"), utc("2024-06-03 17:30")),
        (utc("2024-06-03 17:30"), utc("2024-06-03 18:30")),
        (utc("2024-06-03 18:30"), utc("2024-06-03 19:30")),
        (utc("2024-06-03 19:30"), utc("2024-06-03 20:00")),  # 15:30-16:00, 30 minutes
    ]
    assert session_bins(session, Timeframe.H4) == [
        (utc("2024-06-03 13:30"), utc("2024-06-03 17:30")),
        (utc("2024-06-03 17:30"), utc("2024-06-03 20:00")),
    ]
    assert session_bins(session, Timeframe.D1) == [(session.open, session.close)]


def test_session_bins_on_an_early_close(sessions: list[Session]) -> None:
    session = by_date(sessions, "2024-11-29")  # 09:30-13:00 EST = 14:30-18:00 UTC

    assert session_bins(session, Timeframe.H1) == [
        (utc("2024-11-29 14:30"), utc("2024-11-29 15:30")),
        (utc("2024-11-29 15:30"), utc("2024-11-29 16:30")),
        (utc("2024-11-29 16:30"), utc("2024-11-29 17:30")),
        (utc("2024-11-29 17:30"), utc("2024-11-29 18:00")),
    ]
    assert session_bins(session, Timeframe.H4) == [(session.open, session.close)]
    assert session_bins(session, Timeframe.D1) == [(session.open, session.close)]
