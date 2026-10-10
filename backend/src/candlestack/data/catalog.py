"""Instrument search over the catalogs of both markets (tens of thousands of instruments).

Ranking: the top pair of a crypto base asset equal to the query, the one whose quote asset has
the most pairs in the catalog (``btc`` finds BTCUSDT first, the coin rather than a stock with
that ticker); exact symbol; the other pairs of that base asset, the same way (BTCUSDC before
BTCTRY); symbol prefix; prefix of a word in the name; substring of the symbol; substring of the
name. Other ties go to the shorter symbol, then alphabetically. Symbols are compared without
separators and case (``btc/usdt`` finds ``BTCUSDT``, ``brkb`` finds ``BRK.B``), names word by
word without case and punctuation. Without a query, every instrument comes back in symbol order.
An exchange keeps only the stocks listed on it; crypto pairs have none.
"""

import re
from collections import Counter
from collections.abc import Iterable

import polars as pl

from candlestack.data.models import Exchange, Instrument, InstrumentId, Market

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
                "exchange": [instrument.exchange for instrument in self._items],
                "symbol": [instrument.symbol for instrument in self._items],
                "key": [normalise_query(instrument.symbol) for instrument in self._items],
                "base": [normalise_query(instrument.base or "") for instrument in self._items],
                "quote_pairs": [pairs[instrument.quote or ""] for instrument in self._items],
                "words": [_words(instrument.name) for instrument in self._items],
            },
            schema={
                "market": pl.String,
                "exchange": pl.String,
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

    def search(
        self,
        q: str | None,
        market: Market | None = None,
        limit: int = 20,
        offset: int = 0,
        *,
        exchange: Exchange | None = None,
    ) -> list[Instrument]:
        """Best matches first (see the module docstring); ``None`` lists every instrument by
        symbol, an empty query finds nothing."""
        return self.page(q, market, limit, offset, exchange=exchange)[0]

    def page(
        self,
        q: str | None,
        market: Market | None = None,
        limit: int = 20,
        offset: int = 0,
        *,
        exchange: Exchange | None = None,
    ) -> tuple[list[Instrument], int]:
        """``limit`` matches from ``offset`` on, as ``search`` orders them, and the number of
        all matches."""
        found = self._matches(q, market, exchange)
        total = found.height
        if limit <= 0:
            return [], total
        # Clamped: an offset past the end is an empty page, and polars takes no huge offset.
        page = found.slice(min(offset, total), limit)
        return [self._items[index] for index in page["index"]], total

    def _matches(
        self, q: str | None, market: Market | None, exchange: Exchange | None
    ) -> pl.DataFrame:
        """The ``index`` of every match, in order."""
        frame = self._filter(market, exchange)
        if q is None:
            return frame.sort("symbol", "market").select("index")
        key, words = normalise_query(q), _words(q).lstrip()
        if not key or not words:
            return frame.clear().select("index")
        pair = pl.col("base") == key
        top_pair = pair & (pl.col("quote_pairs") == pl.col("quote_pairs").filter(pair).max())
        rank = (
            pl.when(top_pair)
            .then(0)
            .when(pl.col("key") == key)
            .then(1)
            .when(pair)
            .then(2)
            .when(pl.col("key").str.starts_with(key))
            .then(3)
            .when(pl.col("words").str.contains(f" {words}", literal=True))
            .then(4)
            .when(pl.col("key").str.contains(key, literal=True))
            .then(5)
            .when(pl.col("words").str.contains(words, literal=True))
            .then(6)
        )
        # Pairs of the base asset: the most common quote asset first (USDC before TRY, ...).
        quote_pairs = pl.when(pl.col("rank") == 2).then(pl.col("quote_pairs")).otherwise(0)
        return (
            frame.select("index", "market", "symbol", "quote_pairs", rank.alias("rank"))
            .filter(pl.col("rank").is_not_null())
            .sort(
                "rank",
                quote_pairs,
                pl.col("symbol").str.len_chars(),
                "symbol",
                "market",  # a stable order for paging: equal symbols in both markets
                descending=[False, True, False, False, False],
            )
            .select("index")
        )

    def _filter(self, market: Market | None, exchange: Exchange | None) -> pl.DataFrame:
        frame = self._frame
        if market is not None:
            frame = frame.filter(pl.col("market") == str(market))
        if exchange is not None:
            frame = frame.filter(pl.col("exchange") == str(exchange))
        return frame


def search(
    instruments: Catalog | Iterable[Instrument],
    q: str | None,
    market: Market | None = None,
    limit: int = 20,
    offset: int = 0,
    *,
    exchange: Exchange | None = None,
) -> list[Instrument]:
    """``Catalog.search``; pass a ``Catalog`` to reuse its keys across searches."""
    catalog = instruments if isinstance(instruments, Catalog) else Catalog(instruments)
    return catalog.search(q, market, limit, offset, exchange=exchange)
