"""Asset URL extraction without speculative filename rewriting."""

from __future__ import annotations

from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import Tag
from pydantic import HttpUrl

from prydwen.core.models import AssetLink

from .document import attr


def absolute_url(value: str | None, base: str) -> str | None:
    """Resolve an observed web URL, rejecting executable and inline schemes."""
    if not value or value.startswith("$"):
        return None
    resolved = urljoin(base, value)
    parsed = urlsplit(resolved)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return None
    return resolved


def asset(value: str | None, base: str, alt: str | None = None) -> AssetLink | None:
    """Create a typed link only from a usable source URL."""
    url = absolute_url(value, base)
    return AssetLink(url=HttpUrl(url), alt=alt) if url else None


def image(node: Tag | None, base: str) -> AssetLink | None:
    """Extract direct, lazy, srcset, or recognized optimizer image sources."""
    if node is None:
        return None
    source = attr(node, "src")
    if not source or source.startswith("data:"):
        source = attr(node, "data-src") or attr(node, "data-lazy-src")
    if not source:
        candidates = (attr(node, "srcset") or "").split(",")
        source = candidates[-1].strip().split(" ")[0] if candidates else None
    if not source and node.parent is not None and node.parent.name == "picture":
        sibling = node.parent.select_one("source[srcset]")
        source = (attr(sibling, "srcset") or "").split(",")[-1].strip().split(" ")[0]
    url = absolute_url(source, base)
    if url and urlsplit(url).path == "/_next/image":
        original = parse_qs(urlsplit(url).query).get("url", [None])[0]
        url = absolute_url(original, base) or url
    if not url:
        return None
    dimensions: dict[str, int] = {}
    for key in ("width", "height"):
        value = attr(node, key)
        if value and value.isdecimal() and int(value) > 0:
            dimensions[key] = int(value)
    return AssetLink(url=HttpUrl(url), alt=attr(node, "alt") or None, **dimensions)
