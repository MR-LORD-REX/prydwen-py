"""Async lifecycle and resource loading without game-specific parsing logic."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self, TypeVar

from prydwen.core.cache import JsonCache, default_root
from prydwen.core.models import Dataset, DeliveryInfo, Diagnostic
from prydwen.core.transport import HTMLTransport, PageTransport
from prydwen.exceptions import ClientClosedError, UpstreamSchemaError
from prydwen.parsing.document import Document

Output = TypeVar("Output", bound=Dataset)


class GameClient:
    """Internal shared loader; each game supplies resource models and pure parsers."""

    def __init__(
        self,
        game: str,
        resources: set[str],
        *,
        cache_dir: str | Path | None,
        timeout: float,
        request_interval: float,
        max_response_bytes: int,
        transport: PageTransport | None,
    ) -> None:
        self._cache = JsonCache(default_root(cache_dir), game, resources)
        self._transport = transport or HTMLTransport(timeout, request_interval, max_response_bytes)
        self._owns_transport = transport is None
        self._active = False
        self._closed = False
        self._refreshes = dict.fromkeys(resources, 0)

    async def __aenter__(self) -> Self:
        """Open owned resources and activate this client for data operations."""
        if self._closed or self._active:
            raise ClientClosedError("Client context cannot be reused or nested")
        if isinstance(self._transport, HTMLTransport) and self._owns_transport:
            await self._transport.start()
        self._active = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close owned resources even when a data operation raised an exception."""
        self._active = False
        self._closed = True
        if isinstance(self._transport, HTMLTransport) and self._owns_transport:
            await self._transport.close()

    def _now(self) -> datetime:
        """Provide the current UTC instant for delivery and time-dependent filtering."""
        return datetime.now(UTC)

    async def _load(
        self,
        resource: str,
        url: str,
        model: type[Output],
        parser: Callable[[Document], Output],
        force_new: bool,
    ) -> Output:
        """Read a valid resource cache or fetch, parse, validate, and persist one endpoint."""
        if not self._active:
            raise ClientClosedError("Use an active 'async with Prydwen.Endfield()' context")
        if not isinstance(force_new, bool):
            raise TypeError("force_new must be a bool")
        queued_refresh = self._refreshes[resource]
        async with self._cache.locks[resource]:
            generation = self._cache.generations[resource]
            if not force_new or self._refreshes[resource] > queued_refresh:
                cached = await self._cache.read(resource, model, url)
                if cached is not None:
                    if generation == self._cache.generations[resource]:
                        await self._cache.update_metadata(resource, cached, generation)
                    return cached.model_copy(
                        update={
                            "delivery": DeliveryInfo(from_cache=True, read_at=self._now()),
                        }
                    )
            page = await self._transport.fetch(url)

            def parse() -> Output:
                """Convert required source field failures into a typed schema error."""
                try:
                    return parser(Document(page.html, page.url, page.fetched_at))
                except (KeyError, ValueError, TypeError) as error:
                    raise UpstreamSchemaError(f"Invalid {resource} source data: {error}") from error

            data = await asyncio.to_thread(parse)
            if generation == self._cache.generations[resource]:
                await self._cache.write(resource, data, generation)
                if generation == self._cache.generations[resource]:
                    if not await self._cache.update_metadata(resource, data, generation):
                        data = data.model_copy(
                            update={
                                "diagnostics": [
                                    *data.diagnostics,
                                    Diagnostic(
                                        code="metadata_write_failed",
                                        message="The resource cache is valid; discovery metadata will be rebuilt.",
                                    ),
                                ]
                            }
                        )
                self._refreshes[resource] += 1
            return data.model_copy(
                update={
                    "delivery": DeliveryInfo(from_cache=False, read_at=self._now()),
                }
            )
