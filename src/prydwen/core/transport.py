"""aiohttp requests with bounded threaded Cloudflare fallback and cleanup."""

from __future__ import annotations

import asyncio
import random
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Protocol
from urllib.parse import urljoin, urlsplit

import aiohttp
import cloudscraper
import requests

from prydwen.exceptions import (
    ClientClosedError,
    CloudflareChallengeError,
    HTTPStatusError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    RequestTimeoutError,
)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
REDIRECTS = {301, 302, 303, 307, 308}


@dataclass(frozen=True)
class FetchedPage:
    """A validated HTML response passed to a pure resource parser."""

    html: str
    url: str
    fetched_at: datetime


@dataclass(frozen=True)
class RawResponse:
    """A bounded response before status and challenge classification."""

    status: int
    headers: dict[str, str]
    html: str
    url: str


class PageTransport(Protocol):
    """Injectable transport contract; an injected implementation remains caller-owned."""

    async def fetch(self, url: str) -> FetchedPage:
        """Fetch the requested HTML document or raise a typed request error."""
        ...


def is_challenge(response: RawResponse) -> bool:
    """Recognize Cloudflare interstitials without treating every 403 as a challenge."""
    head = response.html[:100_000].casefold()
    return (
        response.headers.get("cf-mitigated", "").casefold() == "challenge"
        or "/cdn-cgi/challenge-platform/" in head
        or ("<title>just a moment" in head and ("cloudflare" in head or "cf-chl" in head))
    )


class HTMLTransport:
    """Reusable HTTP resources with one serialized requests-based fallback session."""

    def __init__(self, timeout: float = 30, request_interval: float = 10, max_bytes: int = 8_000_000) -> None:
        if timeout <= 0 or request_interval < 0 or max_bytes <= 0:
            raise ValueError("timeout/max_bytes must be positive and request_interval nonnegative")
        self.timeout = timeout
        self.request_interval = request_interval
        self.max_bytes = max_bytes
        self._session: aiohttp.ClientSession | None = None
        self._scraper: Any = None
        self._scraper_lock = threading.Lock()
        self._fallback_gate = asyncio.Semaphore(1)
        self._pace_lock = asyncio.Lock()
        self._next_request = 0.0
        self._fallback_required = False
        self._workers: set[asyncio.Task[RawResponse]] = set()
        self._closed = False

    async def start(self) -> None:
        """Create an owned aiohttp session inside the active event loop."""
        if self._closed:
            raise ClientClosedError("Transport is closed")
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"User-Agent": USER_AGENT},
            )

    async def close(self) -> None:
        """Finish outstanding blocking work before closing either owned session."""
        self._closed = True
        try:
            if self._workers:
                await asyncio.gather(*list(self._workers), return_exceptions=True)
            await asyncio.to_thread(self._close_scraper)
        finally:
            if self._session is not None:
                await self._session.close()

    def _close_scraper(self) -> None:
        """Close the fallback session while respecting its thread serialization."""
        with self._scraper_lock:
            if self._scraper is not None:
                self._scraper.close()
                self._scraper = None

    async def _pace(self) -> None:
        """Reserve a request start using the configured per-client origin interval."""
        async with self._pace_lock:
            loop = asyncio.get_running_loop()
            delay = self._next_request - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_request = loop.time() + self.request_interval

    def _check_url(self, url: str) -> None:
        """Reject off-origin redirects before any request reaches their target."""
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "www.prydwen.gg":
            raise NetworkError(f"Refused page URL outside https://www.prydwen.gg: {url}")

    async def _aio_request(self, url: str) -> RawResponse:
        """Fetch bounded HTML with manually validated redirects."""
        if self._session is None:
            raise ClientClosedError("Transport has not started")
        for _ in range(6):
            self._check_url(url)
            async with self._session.get(url, allow_redirects=False) as response:
                if response.status in REDIRECTS and response.headers.get("Location"):
                    url = urljoin(url, response.headers["Location"])
                    self._check_url(url)
                    await self._pace()
                    continue
                body = bytearray()
                async for chunk in response.content.iter_chunked(65_536):
                    body.extend(chunk)
                    if len(body) > self.max_bytes:
                        raise NetworkError("Response exceeded max_response_bytes")
                return RawResponse(
                    status=response.status,
                    headers={key.casefold(): value for key, value in response.headers.items()},
                    html=body.decode(response.charset or "utf-8", errors="replace"),
                    url=str(response.url),
                )
        raise NetworkError("Too many redirects")

    def _sync_request(self, url: str) -> RawResponse:
        """Run one requests session on a worker with a bounded redirect/body policy."""
        with self._scraper_lock:
            if self._scraper is None:
                self._scraper = cloudscraper.create_scraper()
                self._scraper.headers.update({"User-Agent": USER_AGENT})
            self._check_url(url)
            with self._scraper.get(url, timeout=self.timeout, allow_redirects=False, stream=True) as response:
                body = bytearray()
                for chunk in response.iter_content(chunk_size=65_536):
                    body.extend(chunk)
                    if len(body) > self.max_bytes:
                        raise NetworkError("Response exceeded max_response_bytes")
                return RawResponse(
                    status=response.status_code,
                    headers={key.casefold(): value for key, value in response.headers.items()},
                    html=body.decode(response.encoding or "utf-8", errors="replace"),
                    url=response.url,
                )

    def _worker_finished(self, task: asyncio.Task[RawResponse]) -> None:
        """Observe background failures even when the caller cancelled its await."""
        self._workers.discard(task)
        self._fallback_gate.release()
        if not task.cancelled():
            task.exception()

    async def _fallback_request(self, url: str) -> RawResponse:
        """Keep blocking workers tracked across cancellation and validate redirects."""
        for _ in range(6):
            await self._fallback_gate.acquire()
            try:
                if self._closed:
                    raise ClientClosedError("Transport is closed")
                await self._pace()
                task = asyncio.create_task(asyncio.to_thread(self._sync_request, url))
            except BaseException:
                self._fallback_gate.release()
                raise
            self._workers.add(task)
            task.add_done_callback(self._worker_finished)
            response = await asyncio.shield(task)
            if response.status in REDIRECTS and response.headers.get("location"):
                url = urljoin(url, response.headers["location"])
                self._check_url(url)
                continue
            return response
        raise NetworkError("Too many fallback redirects")

    def _retry_delay(self, response: RawResponse, attempt: int) -> float:
        """Honor bounded Retry-After seconds or HTTP dates before a transient retry."""
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return min(max(float(retry_after), 0), 60)
            except ValueError:
                try:
                    until = parsedate_to_datetime(retry_after)
                    return min(max((until - datetime.now(UTC)).total_seconds(), 0), 60)
                except (ValueError, TypeError):
                    pass
        return 2**attempt + random.uniform(0, 0.5)

    async def fetch(self, url: str) -> FetchedPage:
        """Request HTML, falling back once for recognized challenges and retrying transient failures."""
        await self.start()
        self._check_url(url)
        for attempt in range(3):
            try:
                if self._fallback_required:
                    response = await self._fallback_request(url)
                else:
                    await self._pace()
                    response = await self._aio_request(url)
                if is_challenge(response) and not self._fallback_required:
                    self._fallback_required = True
                    response = await self._fallback_request(url)
            except (aiohttp.ClientError, requests.RequestException, TimeoutError) as error:
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
                    continue
                error_type = (
                    RequestTimeoutError
                    if isinstance(error, (TimeoutError, requests.Timeout))
                    else NetworkError
                )
                raise error_type(f"Request failed for {url}: {error}") from error
            if is_challenge(response):
                raise CloudflareChallengeError(f"Unresolved challenge for {url}")
            if response.status in {429, 500, 502, 503, 504} and attempt < 2:
                await asyncio.sleep(self._retry_delay(response, attempt))
                continue
            if response.status == 404:
                raise NotFoundError(url, 404)
            if response.status == 429:
                raise RateLimitError(url, 429)
            if response.status != 200:
                raise HTTPStatusError(url, response.status)
            if "text/html" not in response.headers.get("content-type", "").casefold():
                raise NetworkError(f"Expected HTML from {url}")
            self._check_url(response.url)
            return FetchedPage(html=response.html, url=response.url, fetched_at=datetime.now(UTC))
        raise NetworkError(f"Retries exhausted for {url}")
