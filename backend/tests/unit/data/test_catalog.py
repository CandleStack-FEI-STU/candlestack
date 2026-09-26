import pytest

from candlestack.data import (
    Catalog,
    Instrument,
    InstrumentId,
    Market,
    normalise_query,
    search,
)


def crypto(symbol: str, base: str, quote: str) -> Instrument:
    return Instrument(
        id=InstrumentId(Market.CRYPTO, symbol),
        name=f"{base}/{quote}",
        source="binance",
        feed="spot",
        base=base,
        quote=quote,
    )


def stock(symbol: str, name: str, exchange: str = "NASDAQ") -> Instrument:
    return Instrument(
        id=InstrumentId(Market.STOCK, symbol),
        name=name,
        source="alpaca",
        feed="iex",
        exchange=exchange,
    )


INSTRUMENTS = [
    crypto("BTCUSDT", "BTC", "USDT"),
    crypto("BTCUSDC", "BTC", "USDC"),
    crypto("WBTCUSDT", "WBTC", "USDT"),
    crypto("ETHBTC", "ETH", "BTC"),
    crypto("ETHUSDT", "ETH", "USDT"),
    crypto("币安人生USDT", "币安人生", "USDT"),
    stock("BTC", "Grayscale Bitcoin Mini Trust ETF", "ARCA"),
    stock("XBTC", "Fund of Abtc Holdings"),
    stock("AAPL", "Apple Inc. Common Stock"),
    stock("APLE", "Apple Hospitality REIT, Inc. Common Stock", "NYSE"),
    stock("BRK.B", "Berkshire Hathaway Inc. Class B", "NYSE"),
    stock("SPY", "SPDR S&P 500 ETF Trust", "ARCA"),
]


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return Catalog(INSTRUMENTS)


def ids(instruments: list[Instrument]) -> list[str]:
    return [str(instrument.id) for instrument in instruments]


@pytest.mark.parametrize(
    ("query", "normalised"),
    [
        ("btc/usdt", "BTCUSDT"),
        ("btc-usdt", "BTCUSDT"),
        ("BTC USDT", "BTCUSDT"),
        ("  btc_usdt ", "BTCUSDT"),
        ("brk.b", "BRKB"),
        ("币安人生usdt", "币安人生USDT"),
        ("", ""),
        (" / - ", ""),
    ],
)
def test_normalise_query(query: str, normalised: str) -> None:
    assert normalise_query(query) == normalised


def test_search_ranks_symbol_then_name_matches(catalog: Catalog) -> None:
    assert ids(catalog.search("btc")) == [
        "crypto:BTCUSDT",  # the top pair of the base asset BTC: its quote has the most pairs
        "stock:BTC",  # exact symbol
        "crypto:BTCUSDC",  # the other pairs of BTC
        "crypto:ETHBTC",  # a word of the name starts with the query (ETH/BTC)
        "stock:XBTC",  # substring of the symbol
        "crypto:WBTCUSDT",
    ]


def test_search_ranks_symbol_prefixes_by_length(catalog: Catalog) -> None:
    assert ids(catalog.search("btcusd")) == [
        "crypto:BTCUSDC",
        "crypto:BTCUSDT",
        "crypto:WBTCUSDT",  # substring of the symbol
    ]
    assert ids(catalog.search("bt", limit=3)) == ["stock:BTC", "crypto:BTCUSDC", "crypto:BTCUSDT"]


def test_base_asset_pairs_come_first_in_a_full_catalog() -> None:
    """``btc`` must find BTCUSDT in the default 20 results among many longer and shorter
    matches, as in the real catalogs (Binance has about 40 BTC pairs)."""
    quotes = ["TRY", "EUR", "BRL", "JPY", "ARS", "PLN", "RON", "ZAR", "USDC", "FDUSD", "USD1"]
    others = [crypto(f"{base}USDT", base, "USDT") for base in ("ETH", "SOL", "XRP", "DOGE")]
    instruments = [
        *(crypto(f"BTC{quote}", "BTC", quote) for quote in quotes),
        crypto("BTCUSDT", "BTC", "USDT"),
        *others,
        *(stock(f"BTC{letter}", f"Bitcoin Fund {letter}") for letter in "CIOWZLMST"),
        stock("BTC", "Grayscale Bitcoin Mini Trust ETF", "ARCA"),
    ]

    found = ids(Catalog(instruments).search("btc", limit=3))

    # Then the other BTC pairs (one pair per quote here): shorter symbol, then alphabetical.
    assert found == ["crypto:BTCUSDT", "stock:BTC", "crypto:BTCARS"]


def test_top_pair_of_a_base_asset_without_a_usdt_pair() -> None:
    instruments = [
        crypto("ABCBTC", "ABC", "BTC"),
        crypto("ABCTRY", "ABC", "TRY"),
        crypto("ETHBTC", "ETH", "BTC"),
        crypto("XRPBTC", "XRP", "BTC"),
        crypto("XRPTRY", "XRP", "TRY"),
        stock("ABC", "American Broadcasting Company"),
    ]

    assert ids(Catalog(instruments).search("abc")) == [
        "crypto:ABCBTC",  # BTC is the quote with the most pairs (3)
        "stock:ABC",
        "crypto:ABCTRY",
    ]


def test_search_name_substring_comes_last(catalog: Catalog) -> None:
    assert ids(catalog.search("bitco")) == ["stock:BTC"]  # word prefix of "Bitcoin"
    assert ids(catalog.search("itcoin")) == ["stock:BTC"]  # substring of the name


@pytest.mark.parametrize("query", ["btc/usdt", "btc-usdt", "BTC USDT", "btcusdt"])
def test_search_ignores_separators_and_case(catalog: Catalog, query: str) -> None:
    assert ids(catalog.search(query))[0] == "crypto:BTCUSDT"


def test_search_by_name_words(catalog: Catalog) -> None:
    assert ids(catalog.search("apple")) == ["stock:AAPL", "stock:APLE"]
    assert ids(catalog.search("Apple Hosp")) == ["stock:APLE"]
    assert ids(catalog.search("s&p 500")) == ["stock:SPY"]


def test_search_dotted_and_non_ascii_symbols(catalog: Catalog) -> None:
    assert ids(catalog.search("brk.b")) == ["stock:BRK.B"]
    assert ids(catalog.search("BRKB")) == ["stock:BRK.B"]
    assert ids(catalog.search("币安")) == ["crypto:币安人生USDT"]


def test_search_market_and_limit(catalog: Catalog) -> None:
    assert ids(catalog.search("btc", market=Market.STOCK)) == ["stock:BTC", "stock:XBTC"]
    assert ids(catalog.search("btc", limit=2)) == ["crypto:BTCUSDT", "stock:BTC"]
    assert catalog.search("btc", limit=0) == []


@pytest.mark.parametrize("query", ["", "   ", "/-.", "zzzz"])
def test_search_without_matches(catalog: Catalog, query: str) -> None:
    assert catalog.search(query) == []


def test_catalog_lookup(catalog: Catalog) -> None:
    assert len(catalog) == len(INSTRUMENTS)
    assert catalog.get(InstrumentId.parse("stock:aapl")) == INSTRUMENTS[8]
    assert catalog.get(InstrumentId.parse("stock:MSFT")) is None
    assert Catalog([]).search("btc") == []


def test_search_function_takes_a_list() -> None:
    assert ids(search(INSTRUMENTS, "eth", market=Market.CRYPTO)) == [
        "crypto:ETHUSDT",
        "crypto:ETHBTC",
    ]
