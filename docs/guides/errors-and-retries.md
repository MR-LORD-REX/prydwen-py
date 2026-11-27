# Errors and retries

All library failures inherit `PrydwenError`. Import concrete exceptions from `prydwen.exceptions`.

```python
from prydwen import Prydwen
from prydwen.exceptions import CloudflareChallengeError, NotFoundError, PrydwenError

try:
    async with Prydwen.Endfield() as endfield:
        piece = await endfield.gear("gear-175")
except NotFoundError as error:
    print(error.url, error.status)
except CloudflareChallengeError:
    print("The source requires interactive verification.")
except PrydwenError as error:
    print(error)
```

- `ClientClosedError`: a method ran outside its active context, or the context was reused.
- `NetworkError` / `RequestTimeoutError`: a request could not complete.
- `HTTPStatusError`, `NotFoundError`, `RateLimitError`: an unsuccessful HTTP result or absent lookup identifier.
- `CloudflareChallengeError`: the recognized challenge remained after fallback.
- `ParseError` / `UpstreamSchemaError`: required page structure or identities changed.
- `CacheError` / `CacheWriteError`: unsafe/unavailable storage or an unsuccessful atomic write.

Invalid method arguments raise `ValueError` or `TypeError` before an unnecessary request. Missing optional fields and unknown labels are diagnostics; a required identity failure is an exception, never an empty successful result.

## Request policy

The default interval between requests is 10 seconds. aiohttp is used first; recognized challenges switch the client to a requests-based cloudscraper session on a serialized worker. Ordinary 403s do not trigger challenge handling. HTTP 429 and transient 5xx/network failures receive bounded retries; `Retry-After` is honored up to 60 seconds per retry. There is no interactive CAPTCHA solver.

Timeouts, maximum body size, TLS validation, and origin checks apply to requests. Cancelled callers do not leave a fallback session in concurrent use: context exit waits for tracked blocking work before closing it. Cancellation cannot forcibly interrupt a running requests call, so cleanup may take up to its network timeout.

```python
async with Prydwen.Endfield(timeout=20, request_interval=10, max_response_bytes=8_000_000) as endfield:
    result = await endfield.tier_list()
```

The package logger has a `NullHandler` and does not print. Configure Python logging in your application if you want cache/debug events.
