"""Market data: instruments and candles from Binance (crypto) and Alpaca (US stocks).

Other modules import only from here (``from candlestack.data import InstrumentId``), never from
the submodules. The contract is docs/data.md.
"""

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

__all__ = [
    "CANDLE_SCHEMA",
    "CandleSet",
    "DataError",
    "DataIntegrityError",
    "Feed",
    "Instrument",
    "InstrumentId",
    "InstrumentNotFound",
    "InvalidRequest",
    "Market",
    "PeriodOutOfRange",
    "Source",
    "SourceUnavailable",
    "Timeframe",
    "TooManyCandles",
    "empty_candles",
]
