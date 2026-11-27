"""Deterministic offline transport for client integration tests."""

import asyncio
from datetime import UTC, datetime

from prydwen.core.transport import FetchedPage

CAPTURE_TIME = datetime(2026, 11, 27, 14, 0, tzinfo=UTC)


class FakeTransport:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages.copy()
        self.calls: list[str] = []
        self.error: Exception | None = None
        self.started = asyncio.Event()
        self.release: asyncio.Event | None = None

    async def fetch(self, url: str) -> FetchedPage:
        self.calls.append(url)
        self.started.set()
        if self.release is not None:
            await self.release.wait()
        await asyncio.sleep(0)
        if self.error is not None:
            raise self.error
        return FetchedPage(self.pages[url.rsplit("/", 1)[-1]], url, CAPTURE_TIME)
