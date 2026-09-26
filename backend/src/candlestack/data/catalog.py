"""Instrument search over the catalogs of both markets (tens of thousands of instruments).

Ranking: exact symbol; the pairs of a crypto base asset equal to the query (``btc`` finds the
BTC pairs), the quote asset with the most pairs in the catalog first (USDT, so BTCUSDT leads);
symbol prefix; prefix of a word in the name; substring of the symbol; substring of the name.
Other ties go to the shorter symbol, then alphabetically. Symbols are compared
without separators and case (``btc/usdt`` finds ``BTCUSDT``, ``brkb`` finds ``BRK.B``), names
word by word without case and punctuation.
"""

import re
from collections import Counter
from collections.abc import Iterable

import polars as pl

from candlestack.data.models import Instrument, InstrumentId, Market

_WORD = re.compile(r"[^\W_]+")


def normalise_query(q: str) -> str:
    """The query as a symbol key: upper-case letters and digits only (``btc/usdt`` ->
    ``BTCUSDT``)."""
    return "".join(char for char in q.upper() if char.isalnum())


def _words(text: str) -> str:
    """Lower-case words separated by single spaces, with a leading space so that ``" " + word``
    finds a word start: ``"Apple Inc."`` -> ``" apple inc"``."""
    return "".join(f" {word}" for word in _WORD.findall(text.lower()))


class Catalog:
    """Instruments of both markets with search keys computed once, and lookup by id."""

    def __init__(self, instruments: Iterable[Instrument]) -> None:
        self._items = list(instruments)
        self._by_id = {instrument.id: instrument for instrument in self._items}
        pairs = Counter(instrument.quote for instrument in self._items if instrument.quote)
        self._frame = pl.DataFrame(
            {
                "market": [str(instrument.market) for instrument in self._items],
                "symbol": [instrument.symbol for instrument in self._items],
                "key": [normalise_query(instrument.symbol) for instrument in self._items],
                "base": [normalise_query(instrument.base or "") for instrument in self._items],
                "quote_pairs": [pairs[instrument.quote or ""] for instrument in self._items],
                "words": [_words(instrument.name) for instrument in self._items],
            },
            schema={
                "market": pl.String,
                "symbol": pl.String,
                "key": pl.String,
                "base": pl.String,
                "quote_pairs": pl.Int64,
                "words": pl.String,
            },
        ).with_row_index("index")

    def __len__(self) -> int:
        return len(self._items)

    def get(self, instrument_id: InstrumentId) -> Instrument | None:
        return self._by_id.get(instrument_id)

    def search(self, q: str, market: Market | None = None, limit: int = 20) -> list[Instrument]:
        """Best matches first (see the module docstring); an empty query finds nothing."""
        key, words = normalise_query(q), _words(q).lstrip()
        if not key or not words or limit <= 0:
            return []
        frame = self._frame
        if market is not None:
            frame = frame.filter(pl.col("market") == str(market))
        rank = (
            pl.when(pl.col("key") == key)
            .then(0)
            .when(pl.col("base") == key)
            .then(1)
            .when(pl.col("key").str.starts_with(key))
            .then(2)
            .when(pl.col("words").str.contains(f" {words}", literal=True))
            .then(3)
            .when(pl.col("key").str.contains(key, literal=True))
            .then(4)
            .when(pl.col("words").str.contains(words, literal=True))
            .then(5)
        )
        # Pairs of the base asset: the most common quote asset first (USDT before TRY, ...).
        quote_pairs = pl.when(pl.col("rank") == 1).then(pl.col("quote_pairs")).otherwise(0)
        found = (
            frame.select("index", "symbol", "quote_pairs", rank.alias("rank"))
            .filter(pl.col("rank").is_not_null())
            .sort(
                "rank",
                quote_pairs,
                pl.col("symbol").str.len_chars(),
                "symbol",
                descending=[False, True, False, False],
            )
            .head(limit)
        )
        return [self._items[index] for index in found["index"]]


def search(
    instruments: Catalog | Iterable[Instrument],
    q: str,
    market: Market | None = None,
    limit: int = 20,
) -> list[Instrument]:
    """``Catalog.search``; pass a ``Catalog`` to reuse its keys across searches."""
    catalog = instruments if isinstance(instruments, Catalog) else Catalog(instruments)
    return catalog.search(q, market, limit)
