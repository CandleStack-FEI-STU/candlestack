"""What an icon is made of: the logo's path at logo.dev, logo.dev's answers and the cache."""

import logging
import xml.etree.ElementTree as ET

import httpx
import pytest

from candlestack.data import Instrument, InstrumentId, Market
from candlestack.data.icons import (
    FALLBACK,
    FALLBACK_AFTER_FAILURE,
    FALLBACK_SVG,
    LOGO_MAX_AGE,
    LOGO_TTL,
    MAX_BYTES,
    NONE_TTL,
    Icon,
    answer,
    decode,
    logo_path,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


def crypto(symbol: str, base: str | None) -> Instrument:
    return Instrument(InstrumentId(Market.CRYPTO, symbol), symbol, "binance", "spot", base=base)


def stock(symbol: str) -> Instrument:
    return Instrument(InstrumentId(Market.STOCK, symbol), symbol, "alpaca", "iex", "NYSE")


@pytest.mark.parametrize(
    ("instrument", "path"),
    [
        (stock("AAPL"), "ticker/AAPL"),
        (stock("BRK.B"), "ticker/BRK.B"),
        (crypto("BTCUSDT", "BTC"), "crypto/BTC"),
        (crypto("1000SATSUSDT", "1000SATS"), "crypto/1000SATS"),
        (crypto("币安人生USDT", "币安人生"), "crypto/%E5%B8%81%E5%AE%89%E4%BA%BA%E7%94%9F"),
        (crypto("XUSDT", None), None),
    ],
)
def test_logo_path(instrument: Instrument, path: str | None) -> None:
    assert logo_path(instrument) == path


@pytest.mark.parametrize("media_type", ["image/png", "image/jpeg", "image/webp"])
def test_a_logo_is_kept_with_its_type(media_type: str) -> None:
    response = httpx.Response(200, content=PNG, headers={"Content-Type": media_type})

    blob, ttl = answer("ticker/AAPL", response)

    assert ttl == LOGO_TTL
    assert decode(blob) == Icon(PNG, media_type, LOGO_MAX_AGE)


def test_the_type_is_read_without_its_parameters() -> None:
    response = httpx.Response(200, content=PNG, headers={"Content-Type": "Image/PNG; q=1"})

    assert decode(answer("ticker/AAPL", response)[0]).media_type == "image/png"


def test_no_logo_is_kept_for_days() -> None:
    blob, ttl = answer("ticker/ZZZZ", httpx.Response(404, json={"error": "not found"}))

    assert ttl == NONE_TTL
    assert decode(blob) == FALLBACK


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="oops"),
        httpx.Response(429, headers={"Retry-After": "30"}),
        httpx.Response(200, content=b"<svg/>", headers={"Content-Type": "image/svg+xml"}),
        httpx.Response(200, text="<html>hi</html>", headers={"Content-Type": "text/html"}),
        httpx.Response(200, content=PNG),
        httpx.Response(200, content=b"", headers={"Content-Type": "image/png"}),
        httpx.Response(
            200, content=b"\x00" * (MAX_BYTES + 1), headers={"Content-Type": "image/png"}
        ),
    ],
    ids=["5xx", "429", "svg", "html", "no-type", "empty", "too-large"],
)
def test_anything_else_is_a_failure_for_a_minute(
    response: httpx.Response, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        blob, ttl = answer("ticker/AAPL", response)

    assert ttl == 60
    assert decode(blob) == FALLBACK_AFTER_FAILURE
    assert "ticker/AAPL" in caplog.text


@pytest.mark.parametrize("status", [401, 403])
def test_a_rejected_key_is_an_error(status: int, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        blob, ttl = answer("ticker/AAPL", httpx.Response(status, json={"error": "bad token"}))

    assert (decode(blob), ttl) == (FALLBACK_AFTER_FAILURE, 60)
    assert [record.levelname for record in caplog.records] == ["ERROR"]
    assert f"rejected our key (HTTP {status})" in caplog.text


def test_the_fallback_is_a_valid_svg() -> None:
    root = ET.fromstring(FALLBACK_SVG)

    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert (root.get("width"), root.get("height")) == ("64", "64")
    assert FALLBACK.media_type == FALLBACK_AFTER_FAILURE.media_type == "image/svg+xml"
    assert (FALLBACK.max_age, FALLBACK_AFTER_FAILURE.max_age) == (3600, 60)
