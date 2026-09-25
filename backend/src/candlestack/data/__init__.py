"""Market data: instruments and candles from Binance (crypto) and Alpaca (US stocks).

Other modules import only from here (``from candlestack.data import InstrumentId``), never from
the submodules. The contract is docs/data.md.
"""

from candlestack.data.candles import (
    MAX_GAP_RANGES,
    Gaps,
    candle_count,
    closed_only,
    expected_bins_fixed,
    expected_bins_sessions,
    find_gaps,
    fingerprint,
    normalise,
    resample_fixed,
    resample_sessions,
    slice_range,
    suggest,
    validate,
)
from candlestack.data.errors import (
    DataError,
    DataIntegrityError,
    InstrumentNotFound,
    InvalidRequest,
    PeriodOutOfRange,
    SourceUnavailable,
    TooManyCandles,
)
from candlestack.data.models import (
    CANDLE_SCHEMA,
    CandleSet,
    Feed,
    Instrument,
    InstrumentId,
    Market,
    Source,
    Timeframe,
    empty_candles,
)
from candlestack.data.sessions import Session, parse_calendar, session_bins, sessions_between

__all__ = [
    "CANDLE_SCHEMA",
    "MAX_GAP_RANGES",
    "CandleSet",
    "DataError",
    "DataIntegrityError",
    "Feed",
    "Gaps",
    "Instrument",
    "InstrumentId",
    "InstrumentNotFound",
    "InvalidRequest",
    "Market",
    "PeriodOutOfRange",
    "Session",
    "Source",
    "SourceUnavailable",
    "Timeframe",
    "TooManyCandles",
    "candle_count",
    "closed_only",
    "empty_candles",
    "expected_bins_fixed",
    "expected_bins_sessions",
    "find_gaps",
    "fingerprint",
    "normalise",
    "parse_calendar",
    "resample_fixed",
    "resample_sessions",
    "session_bins",
    "sessions_between",
    "slice_range",
    "suggest",
    "validate",
]
