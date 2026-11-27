# Prydwen client

```python
from prydwen import Prydwen
```

`Prydwen.Endfield` is the Endfield client constructor, available without constructing the facade. Adding another game exposes its own client in the same namespace.

## Endfield constructor

```python
Prydwen.Endfield(
    *,
    cache_dir=None,
    timeout=30,
    request_interval=10,
    max_response_bytes=8_000_000,
    transport=None,
)
```

- `cache_dir`: string or Path cache root; default `<cwd>/.prywen_cache` captured at construction.
- `timeout`: positive request timeout in seconds.
- `request_interval`: nonnegative delay between request starts; default 10 seconds follows the inspected source crawl guidance.
- `max_response_bytes`: positive decoded-response limit.
- `transport`: optional implementation of the internal `PageTransport` protocol. Injected transports remain caller-owned; the normal client owns and closes its HTTP sessions.

Construction and imports do not fetch data or create cache directories. Use one active asynchronous context. A closed client cannot be reopened, and contexts cannot be nested.

## Clear cache

```python
await Prydwen.clear_cache(game=None, *, resource=None, cache_dir=None)
```

`game` accepts `"arknights-endfield"` or None for all supported games. `resource` selects a known resource key or None for the whole game. Resource and game names are validated; arbitrary filesystem paths are not accepted as selectors. Use `cache_dir` to match a client's custom root.

This operation requires no HTTP client and makes no requests. A missing cache is harmless. Unsafe linked targets and filesystem failures raise `CacheError`.
