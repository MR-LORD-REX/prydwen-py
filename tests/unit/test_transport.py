import asyncio
import threading
from unittest.mock import AsyncMock

import pytest

from prydwen.core.transport import HTMLTransport, RawResponse, is_challenge
from prydwen.exceptions import (
    CloudflareChallengeError,
    HTTPStatusError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    RequestTimeoutError,
)

URL = "https://www.prydwen.gg/arknights-endfield/characters"


def response(status=200, html="<html>Resource</html>", headers=None):
    return RawResponse(status, {"content-type": "text/html", **(headers or {})}, html, URL)


@pytest.mark.parametrize("status", [200, 403, 503])
def test_challenge_detection_is_independent_of_status(status):
    assert is_challenge(
        response(
            status, '<title>Just a moment...</title><script src="/cdn-cgi/challenge-platform/test"></script>'
        )
    )
    assert not is_challenge(response(403, "<html>Permission denied</html>"))


async def test_aiohttp_success_without_fallback(monkeypatch):
    transport = HTMLTransport(request_interval=0)
    primary = AsyncMock(return_value=response())
    fallback = AsyncMock()
    monkeypatch.setattr(transport, "_aio_request", primary)
    monkeypatch.setattr(transport, "_fallback_request", fallback)
    try:
        page = await transport.fetch(URL)
        assert page.url == URL and "<html>" in page.html
        fallback.assert_not_called()
    finally:
        await transport.close()


async def test_challenge_uses_one_fallback_and_remembers_origin(monkeypatch):
    transport = HTMLTransport(request_interval=0)
    primary = AsyncMock(return_value=response(403, headers={"cf-mitigated": "challenge"}))
    fallback = AsyncMock(return_value=response())
    monkeypatch.setattr(transport, "_aio_request", primary)
    monkeypatch.setattr(transport, "_fallback_request", fallback)
    try:
        await transport.fetch(URL)
        await transport.fetch(URL)
        assert primary.await_count == 1 and fallback.await_count == 2
    finally:
        await transport.close()


async def test_unresolved_challenge_does_not_cache_or_loop(monkeypatch):
    transport = HTMLTransport(request_interval=0)
    challenge = response(403, headers={"cf-mitigated": "challenge"})
    primary = AsyncMock(return_value=challenge)
    fallback = AsyncMock(return_value=challenge)
    monkeypatch.setattr(transport, "_aio_request", primary)
    monkeypatch.setattr(transport, "_fallback_request", fallback)
    try:
        with pytest.raises(CloudflareChallengeError):
            await transport.fetch(URL)
        assert primary.await_count == fallback.await_count == 1
    finally:
        await transport.close()


@pytest.mark.parametrize(
    "status,error", [(403, HTTPStatusError), (404, NotFoundError), (429, RateLimitError)]
)
async def test_status_errors_are_distinct(status, error, monkeypatch):
    transport = HTMLTransport(request_interval=0)
    primary = AsyncMock(return_value=response(status))
    monkeypatch.setattr(transport, "_aio_request", primary)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    try:
        with pytest.raises(error):
            await transport.fetch(URL)
        assert primary.await_count == (3 if status == 429 else 1)
    finally:
        await transport.close()


async def test_timeout_retries_are_bounded(monkeypatch):
    transport = HTMLTransport(request_interval=0)
    primary = AsyncMock(side_effect=TimeoutError("timed out"))
    monkeypatch.setattr(transport, "_aio_request", primary)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    try:
        with pytest.raises(RequestTimeoutError):
            await transport.fetch(URL)
        assert primary.await_count == 3
    finally:
        await transport.close()


async def test_retry_after_and_invalid_content(monkeypatch):
    transport = HTMLTransport(request_interval=0)
    primary = AsyncMock(side_effect=[response(429, headers={"retry-after": "7"}), response()])
    sleep = AsyncMock()
    monkeypatch.setattr(transport, "_aio_request", primary)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    try:
        await transport.fetch(URL)
        sleep.assert_awaited_once_with(7)
        primary.side_effect = None
        primary.return_value = response(headers={"content-type": "application/json"})
        with pytest.raises(NetworkError, match="Expected HTML"):
            await transport.fetch(URL)
    finally:
        await transport.close()


async def test_blocking_fallback_does_not_block_loop_and_is_tracked_after_cancel(monkeypatch):
    transport = HTMLTransport(request_interval=0)
    entered = threading.Event()
    release = threading.Event()
    main_thread = threading.get_ident()

    def blocking(url):
        assert threading.get_ident() != main_thread
        entered.set()
        assert release.wait(3)
        return response()

    monkeypatch.setattr(transport, "_sync_request", blocking)
    task = asyncio.create_task(transport._fallback_request(URL))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        assert not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert transport._workers
        release.set()
        await transport.close()
        assert not transport._workers
    finally:
        release.set()
        await transport.close()


def test_url_allowlist():
    transport = HTMLTransport()
    for url in [
        "http://www.prydwen.gg/page",
        "https://evil.example/page",
        "https://www.prydwen.gg@evil.example/page",
    ]:
        with pytest.raises(NetworkError):
            transport._check_url(url)


@pytest.mark.parametrize("kwargs", [{"timeout": 0}, {"request_interval": -1}, {"max_bytes": 0}])
def test_invalid_transport_configuration(kwargs):
    with pytest.raises(ValueError):
        HTMLTransport(**kwargs)


class AsyncBody:
    def __init__(self, chunks):
        self.chunks = chunks

    async def iter_chunked(self, size):
        for chunk in self.chunks:
            yield chunk


class HTTPResponse:
    def __init__(self, chunks=(), status=200, headers=None, url=URL):
        self.status = status
        self.headers = headers or {"Content-Type": "text/html"}
        self.content = AsyncBody(chunks)
        self.charset = "utf-8"
        self.url = url

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


class HTTPSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)

    async def close(self):
        return None


async def test_aiohttp_reader_limits_streamed_body():
    transport = HTMLTransport(request_interval=0, max_bytes=8)
    transport._session = HTTPSession([HTTPResponse([b"12345", b"6789"])])
    try:
        with pytest.raises(NetworkError, match="max_response_bytes"):
            await transport._aio_request(URL)
    finally:
        await transport.close()


async def test_redirect_is_validated_before_following():
    transport = HTMLTransport(request_interval=0)
    session = HTTPSession([HTTPResponse(status=302, headers={"Location": "https://evil.example"})])
    transport._session = session
    try:
        with pytest.raises(NetworkError, match="outside"):
            await transport._aio_request(URL)
        assert len(session.calls) == 1
    finally:
        await transport.close()


async def test_same_origin_redirect_preserves_manual_policy():
    transport = HTMLTransport(request_interval=0)
    destination = "https://www.prydwen.gg/arknights-endfield/characters/"
    session = HTTPSession(
        [
            HTTPResponse(status=301, headers={"Location": destination}),
            HTTPResponse([b"<html>OK</html>"], url=destination),
        ]
    )
    transport._session = session
    try:
        result = await transport._aio_request(URL)
        assert result.html == "<html>OK</html>" and result.url == destination
        assert [call[0] for call in session.calls] == [URL, destination]
        assert all(call[1] == {"allow_redirects": False} for call in session.calls)
    finally:
        await transport.close()


async def test_requests_are_paced(monkeypatch):
    transport = HTMLTransport(request_interval=10)
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)
    await transport._pace()
    await transport._pace()
    sleep.assert_awaited_once()
    assert 9 < sleep.await_args.args[0] <= 10


async def test_fallback_waiters_do_not_start_extra_workers(monkeypatch):
    transport = HTMLTransport(request_interval=0)
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def blocking(url):
        calls.append(url)
        entered.set()
        assert release.wait(3)
        return response()

    monkeypatch.setattr(transport, "_sync_request", blocking)
    tasks = [asyncio.create_task(transport._fallback_request(URL)) for _ in range(4)]
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        assert len(transport._workers) == len(calls) == 1
        release.set()
        results = await asyncio.gather(*tasks)
        assert len(calls) == len(results) == 4
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        await transport.close()
