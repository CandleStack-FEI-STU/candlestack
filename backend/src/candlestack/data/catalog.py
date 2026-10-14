"""Instrument search over the catalogs of both markets (tens of thousands of instruments).

Ranking: the top pair of a crypto base asset equal to the query, the one whose quote asset has
the most pairs in the catalog (``btc`` finds BTCUSDT first, the coin rather than a stock with
that ticker); exact symbol; the other pairs of that base asset, the same way (BTCUSDC before
BTCTRY); symbol prefix; prefix of a word in the name; substring of the symbol; substring of the
name. Other ties go to the chosen sort (24 h volume by default), then to the shorter symbol,
then alphabetically. Symbols are compared without separators and case (``btc/usdt`` finds
``BTCUSDT``, ``brkb`` finds ``BRK.B``), names word by word without case and punctuation. Without
a query, every instrument comes back in the chosen sort: by 24 h volume, by 24 h change (either
way) or by symbol; instruments without stats come last in the stats sorts. An exchange keeps
only the instruments that trade on it (BINANCE: the crypto pairs).
"""

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

import polars as pl

from candlestack.data.models import (
    STATS_SCHEMA,
    Exchange,
    Instrument,
    InstrumentId,
    InstrumentSort,
    InstrumentStats,
    Market,
)

_WORD = re.compile(r"[^\W_]+")
_STATS = ["price", "change_24h", "volume_24h"]
# The stats of the instruments of both markets: ``STATS_SCHEMA`` with the market first.
MARKET_STATS_SCHEMA = pl.Schema({"market": pl.String, **STATS_SCHEMA})
# The sort key that comes before the other ties, and whether it is descending; none for symbol.
_SORT_KEYS = {
    InstrumentSort.VOLUME: ("volume_24h", True),
    InstrumentSort.CHANGE: ("change_24h", True),
    InstrumentSort.LOSERS: ("change_24h", False),
}


@dataclass(frozen=True, slots=True)
class CatalogPage:
    """A page of matches, best first, the stats of each (``None`` without), and the number of
    all matches."""

    items: list[Instrument]
    stats: list[InstrumentStats | None]
    total: int


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
        # The catalog joined with the stats it was last searched with, kept while they are the
        # same frame (the store hands out one frame until its stats change).
        self._joined: tuple[pl.DataFrame | None, pl.DataFrame] = (None, self._with_stats(None))

    def __len__(self) -> int:
        return len(self._items)

    def get(self, instrument_id: InstrumentId) -> Instrument | None:
        return self._by_id.get(instrument_id)

    def instruments(self, market: Market) -> list[Instrument]:
        """Every instrument of the market."""
        return [instrument for instrument in self._items if instrument.market is market]

    # The query and its filters, then how to order it (keyword-only).
    def search(  # noqa: PLR0913
        self,
        q: str | None,
        market: Market | None = None,
        limit: int = 20,
        offset: int = 0,
        *,
        exchange: Exchange | None = None,
        sort: InstrumentSort = InstrumentSort.VOLUME,
        stats: pl.DataFrame | None = None,
    ) -> list[Instrument]:
        """Best matches first (see the module docstring); ``None`` lists every instrument in the
        sort, an empty query finds nothing. ``stats`` (``MARKET_STATS_SCHEMA``) gives the
        numbers to sort by; without them every instrument counts as one without stats."""
        return self.page(q, market, limit, offset, exchange=exchange, sort=sort, stats=stats).items

    def page(  # noqa: PLR0913
        self,
        q: str | None,
        market: Market | None = None,
        limit: int = 20,
        offset: int = 0,
        *,
        exchange: Exchange | None = None,
        sort: InstrumentSort = InstrumentSort.VOLUME,
        stats: pl.DataFrame | None = None,
    ) -> CatalogPage:
        """``limit`` matches from ``offset`` on, as ``search`` orders them, with their stats, and
        the number of all matches."""
        found = self._matches(q, market, exchange, sort, stats)
        total = found.height
        if limit <= 0:
            return CatalogPage([], [], total)
        # Clamped: an offset past the end is an empty page, and polars takes no huge offset.
        page = found.slice(min(offset, total), limit)
        return CatalogPage(
            [self._items[index] for index in page["index"]],
            [
                None if price is None else InstrumentStats(price, change, volume)
                for price, change, volume in page.select(_STATS).iter_rows()
            ],
            total,
        )

    def _matches(
        self,
        q: str | None,
        market: Market | None,
        exchange: Exchange | None,
        sort: InstrumentSort,
        stats: pl.DataFrame | None,
    ) -> pl.DataFrame:
        """The ``index`` and the stats of every match, in order."""
        frame = self._filter(self._joined_with(stats), market, exchange)
        columns = ["index", *_STATS]
        # Instruments without stats go last in the stats sorts, whichever way they sort.
        by: list[pl.Expr] = []
        descending: list[bool] = []
        if sort in _SORT_KEYS:
            column, down = _SORT_KEYS[sort]
            by, descending = [pl.col(column)], [down]
        if q is None:
            return frame.sort(
                [*by, pl.col("symbol"), pl.col("market")],
                descending=[*descending, False, False],
                nulls_last=True,
            ).select(columns)
        key, words = normalise_query(q), _words(q).lstrip()
        if not key or not words:
            return frame.clear().select(columns)
        rank = _rank(key, words)
        # Pairs of the base asset: the most common quote asset first (USDC before TRY, ...).
        quote_pairs = pl.when(pl.col("rank") == 2).then(pl.col("quote_pairs")).otherwise(0)
        # The ranking first; the chosen sort only breaks its ties, before the shorter symbol.
        return (
            frame.with_columns(rank.alias("rank"))
            .filter(pl.col("rank").is_not_null())
            .sort(
                [
                    pl.col("rank"),
                    quote_pairs,
                    *by,
                    pl.col("symbol").str.len_chars(),
                    pl.col("symbol"),
                    pl.col("market"),  # a stable order for paging: equal symbols in both markets
                ],
                descending=[False, True, *descending, False, False, False],
                nulls_last=True,
            )
            .select(columns)
        )

    def _joined_with(self, stats: pl.DataFrame | None) -> pl.DataFrame:
        """The catalog with the columns of ``stats``, joined once per stats frame."""
        joined_stats, joined = self._joined
        if stats is not joined_stats:
            joined = self._with_stats(stats)
            self._joined = (stats, joined)
        return joined

    def _with_stats(self, stats: pl.DataFrame | None) -> pl.DataFrame:
        return self._frame.join(
            pl.DataFrame(schema=MARKET_STATS_SCHEMA) if stats is None else stats,
            on=["market", "symbol"],
            how="left",
            maintain_order="left",
        )

    @staticmethod
    def _filter(
        frame: pl.DataFrame, market: Market | None, exchange: Exchange | None
    ) -> pl.DataFrame:
        if market is not None:
            frame = frame.filter(pl.col("market") == str(market))
        if exchange is not None:
            frame = frame.filter(pl.col("exchange") == str(exchange))
        return frame


def _rank(key: str, words: str) -> pl.Expr:
    """The rank of a match (0 best, null for no match) for the query's symbol key and words."""
    pair = pl.col("base") == key
    top_pair = pair & (pl.col("quote_pairs") == pl.col("quote_pairs").filter(pair).max())
    return (
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


# The query and its filters, then how to order it (keyword-only).
def search(  # noqa: PLR0913
    instruments: Catalog | Iterable[Instrument],
    q: str | None,
    market: Market | None = None,
    limit: int = 20,
    offset: int = 0,
    *,
    exchange: Exchange | None = None,
    sort: InstrumentSort = InstrumentSort.VOLUME,
    stats: pl.DataFrame | None = None,
) -> list[Instrument]:
    """``Catalog.search``; pass a ``Catalog`` to reuse its keys across searches."""
    catalog = instruments if isinstance(instruments, Catalog) else Catalog(instruments)
    return catalog.search(q, market, limit, offset, exchange=exchange, sort=sort, stats=stats)
