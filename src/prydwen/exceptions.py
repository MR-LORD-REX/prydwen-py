"""Errors raised by transport, parsing, storage, and resource lookups."""


class PrydwenError(Exception):
    """Base error for the library."""


class ClientClosedError(PrydwenError):
    """An operation requires an active client context."""


class NetworkError(PrydwenError):
    """A request could not complete."""


class RequestTimeoutError(NetworkError):
    """A request exceeded its configured timeout."""


class HTTPStatusError(NetworkError):
    """A server returned an unsuccessful HTTP status."""

    def __init__(self, url: str, status: int) -> None:
        self.url = url
        self.status = status
        super().__init__(f"HTTP {status} while requesting {url}")


class NotFoundError(HTTPStatusError):
    """A page or an identifier does not exist in the selected resource."""


class RateLimitError(HTTPStatusError):
    """The upstream server rejected a request after bounded retries."""


class CloudflareChallengeError(NetworkError):
    """A challenge remained after the fallback request."""


class ParseError(PrydwenError):
    """A page cannot be interpreted as the expected resource."""


class UpstreamSchemaError(ParseError):
    """Required source records or fields no longer match the parser contract."""


class CacheError(PrydwenError):
    """The cache cannot be accessed safely."""


class CacheWriteError(CacheError):
    """A parsed resource could not be persisted."""
