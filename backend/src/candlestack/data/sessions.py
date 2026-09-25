"""US stock market sessions (the regular session of each NYSE trading day) and their bins."""

import bisect
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from candlestack.data.errors import DataIntegrityError
from candlestack.data.models import Timeframe

NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class Session:
    """One trading day: ``open`` and ``close`` of its regular session in UTC epoch seconds."""

    date: date
    open: int
    close: int


def parse_calendar(items: Iterable[Mapping[str, Any]]) -> list[Session]:
    """Sessions from Alpaca ``GET /v2/calendar`` items, sorted by date.

    An item has ``date`` (``YYYY-MM-DD``) and ``open``/``close`` (``HH:MM``, New York wall
    clock), e.g. ``{"date": "2024-11-29", "open": "09:30", "close": "13:00"}``. zoneinfo makes
    the conversion DST-correct: 09:30 is 14:30 UTC in winter and 13:30 UTC in summer. Raises
    ``DataIntegrityError`` on a malformed item.
    """
    sessions = []
    for item in items:
        try:
            day = date.fromisoformat(item["date"])
            opens = _new_york(day, item["open"])
            closes = _new_york(day, item["close"])
        except (KeyError, TypeError, ValueError) as error:
            raise DataIntegrityError(f"Malformed trading calendar day {item!r}: {error}") from None
        if opens >= closes:
            raise DataIntegrityError(f"Trading calendar day {item!r} closes before it opens")
        sessions.append(Session(day, opens, closes))
    return sorted(sessions, key=lambda session: session.date)


def _new_york(day: date, clock: str) -> int:
    if len(clock) != 5:
        raise ValueError(f"time {clock!r} is not HH:MM")
    return int(datetime.combine(day, time.fromisoformat(clock), NEW_YORK).timestamp())


def sessions_between(sessions: Sequence[Session], start: int, end: int) -> list[Session]:
    """Sessions that overlap ``[start, end)``; ``sessions`` sorted by date."""
    first = bisect.bisect_right(sessions, start, key=lambda session: session.close)
    found = []
    for session in sessions[first:]:
        if session.open >= end:
            break
        found.append(session)
    return found


def session_bins(session: Session, timeframe: Timeframe) -> list[tuple[int, int]]:
    """``(open, close)`` of each candle of a session, aligned to the session open.

    The last bin ends at the session close and can be shorter than the timeframe: on a normal
    day 1h gives 09:30, 10:30, ..., 15:30-16:00 and 4h gives 09:30-13:30 and 13:30-16:00; 1d
    is the whole session.
    """
    step = timeframe.seconds
    return [
        (opens, min(opens + step, session.close))
        for opens in range(session.open, session.close, step)
    ]
