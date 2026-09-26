"""The instrument catalogs of both markets, kept in Redis and in process memory.

Each market's list is one Redis value (``data:v1:catalog:<market>``, compact JSON with its
fetch time). A list older than 24 hours is still served at once while one background task
refreshes it from the source. Searches run on an in-process ``Catalog``; when the process's
copy is stale it first adopts a newer list another process already stored. Once one market is
loaded, a search over all markets does not wait for the others: they are loaded in the
background and the search answers from the loaded ones.
"""

import asyncio
import logging
import time
from collections.abc import Coroutine, Mapping
from dataclasses import dataclass
from typing import Any

import orjson
from anyio import to_thread

from candlestack.data.cache import Cache
from candlestack.data.catalog import Catalog
from candlestack.data.errors import DataError, DataIntegrityError
from candlestack.data.models import Instrument, InstrumentId, Market
from candlestack.data.sources.base import DAY, DataSource

logger = logging.getLogger(__name__)

REFRESH_AFTER = DAY
# Redis keeps a list this long, so a stale one can be served while the source is down.
KEEP_TTL = 7 * DAY
# A background refresh is not started again sooner than this.
RETRY_SECONDS = 300
# After a catalog failed to load, requests get the same error this long without a new try.
LOAD_RETRY_SECONDS = 30

# Patched by tests to move the clock.
_time = time.time


@dataclass(frozen=True, slots=True)
class _Entry:
    fetched_at: int
    instruments: list[Instrument]


class CatalogStore:
    def __init__(self, cache: Cache, sources: Mapping[Market, DataSource]) -> None:
        self._cache = cache
        self._sources = sources
        self._entries: dict[Market, _Entry] = {}
        self._catalog: Catalog | None = None
        self._version = 0  # bumped whenever an entry changes
        self._next_refresh: dict[Market, float] = {}
        self._failed: dict[Market, tuple[float, DataError]] = {}
        self._loading: set[Market] = set()
        self._tasks: set[asyncio.Task[None]] = set()

    async def catalog(self, market: Market | None = None) -> Catalog:
        """A catalog with the instruments of ``market``, or of every market that can be loaded
        (``missing`` names the markets left out). Raises the source's error when no requested
        market can be loaded.

        Markets are waited for only while none of the requested ones is loaded. Once one is, the
        others are loaded in the background and left out until they are, so a source that is
        down does not hold up a search over all markets for its timeout.
        """
        markets = [market] if market else list(self._sources)
        waited = [each for each in markets if each in self._entries] or markets
        for each in markets:
            if each not in waited:
                self._load_in_background(each)
        results = await asyncio.gather(
            *(self._entry(each) for each in waited), return_exceptions=True
        )
        errors = [result for result in results if isinstance(result, BaseException)]
        for error in errors:
            if not isinstance(error, DataError):
                raise error
        if len(errors) == len(markets):
            raise errors[0]
        if self._catalog is not None:
            return self._catalog
        version = self._version
        catalog = await to_thread.run_sync(
            Catalog,
            [
                item
                for each in Market
                if each in self._entries
                for item in self._entries[each].instruments
            ],
        )
        if version == self._version:  # no newer entry arrived while it was built
            self._catalog = catalog
        return catalog

    def missing(self, market: Market | None = None) -> list[Market]:
        """The requested markets (all without ``market``) whose list is not loaded, which a
        catalog leaves out."""
        markets = [market] if market else list(self._sources)
        return [each for each in markets if each not in self._entries]

    async def _entry(self, market: Market) -> _Entry:
        entry = self._entries.get(market)
        if entry is None:
            entry = await self._load(market)
        if _time() - entry.fetched_at >= REFRESH_AFTER:
            self._refresh_in_background(market)
        return entry

    async def _load(self, market: Market) -> _Entry:
        """The list from Redis, else from the source (single-flight)."""
        retry_at, error = self._failed.get(market, (0.0, None))
        if error is not None and time.monotonic() < retry_at:
            raise error.with_traceback(None)
        try:
            blob = await self._cache.get_or_fetch(f"catalog:{market}", lambda: self._fetch(market))
        except DataError as exc:
            logger.warning("The %s catalog cannot be loaded: %s", market, exc.detail)
            self._failed[market] = (time.monotonic() + LOAD_RETRY_SECONDS, exc)
            raise
        entry = await to_thread.run_sync(self._decode, market, blob)
        self._adopt(market, entry)
        return entry

    async def _fetch(self, market: Market) -> tuple[bytes, int]:
        instruments = await self._sources[market].list_instruments()
        items = [[i.symbol, i.name, i.exchange, i.base, i.quote] for i in instruments]
        return orjson.dumps({"fetched_at": int(_time()), "items": items}), KEEP_TTL

    def _decode(self, market: Market, blob: bytes) -> _Entry:
        source = self._sources[market]
        try:
            value = orjson.loads(blob)
            instruments = [
                Instrument(
                    id=InstrumentId(market, symbol),
                    name=name,
                    source=source.name,
                    feed=source.feed,
                    exchange=exchange,
                    base=base,
                    quote=quote,
                )
                for symbol, name, exchange, base, quote in value["items"]
            ]
            return _Entry(int(value["fetched_at"]), instruments)
        except (orjson.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise DataIntegrityError(f"The cached {market} catalog cannot be read: {exc}") from None

    def _adopt(self, market: Market, entry: _Entry) -> None:
        current = self._entries.get(market)
        if current is None or entry.fetched_at > current.fetched_at:
            self._entries[market] = entry
            self._catalog = None
            self._version += 1

    def _load_in_background(self, market: Market) -> None:
        """Loads a market's list unless it is loading or failed less than
        ``LOAD_RETRY_SECONDS`` ago."""
        retry_at, _ = self._failed.get(market, (0.0, None))
        if market in self._loading or time.monotonic() < retry_at:
            return
        self._loading.add(market)
        self._start(self._load_quietly(market))

    async def _load_quietly(self, market: Market) -> None:
        try:
            await self._load(market)
        except DataError:
            pass  # _load logged it and answers with it until the next retry
        except Exception:
            logger.exception("Loading the %s catalog failed", market)
        finally:
            self._loading.discard(market)

    def _start(self, work: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(work)
        self._tasks.add(task)  # a task without a reference can be garbage-collected
        task.add_done_callback(self._tasks.discard)

    def _refresh_in_background(self, market: Market) -> None:
        if time.monotonic() < self._next_refresh.get(market, 0.0):
            return
        self._next_refresh[market] = time.monotonic() + RETRY_SECONDS
        self._start(self._refresh(market))

    async def _refresh(self, market: Market) -> None:
        name = f"catalog:{market}"
        try:
            stored = await self._cache.get(name)
            if stored is not None:
                entry = await to_thread.run_sync(self._decode, market, stored)
                if _time() - entry.fetched_at < REFRESH_AFTER:
                    self._adopt(market, entry)  # another process refreshed it already
                    return
            token = await self._cache.lock(name)
            if token is None:
                return  # another process is refreshing it; adopted on the next attempt
            try:
                blob, ttl = await self._fetch(market)
                await self._cache.set(name, blob, ttl)
            finally:
                await self._cache.unlock(name, token)
            self._adopt(market, await to_thread.run_sync(self._decode, market, blob))
            logger.info("Refreshed the %s catalog", market)
        except DataError as exc:
            logger.warning("Refreshing the %s catalog failed: %s", market, exc.detail)
        except Exception:
            logger.exception("Refreshing the %s catalog failed", market)
