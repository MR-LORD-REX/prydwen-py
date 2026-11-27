"""Scoped document extraction and provenance for downloaded HTML."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup, Tag
from pydantic import HttpUrl

from prydwen.core.models import Diagnostic, SourceInfo
from prydwen.exceptions import UpstreamSchemaError

from .embedded import collection, inline_records


def attr(node: Tag | None, key: str) -> str | None:
    """Read a scalar HTML attribute without treating class arrays as text."""
    value = node.get(key) if node is not None else None
    return value if isinstance(value, str) else None


def text(node: Tag | None) -> str:
    """Normalize whitespace while preserving textual word boundaries."""
    return " ".join(node.get_text(" ", strip=True).split()) if node is not None else ""


def classes(node: Tag) -> list[str]:
    """Read the class attribute consistently across Beautiful Soup versions."""
    value = node.get("class")
    if isinstance(value, str):
        return value.split()
    return list(value) if value is not None else []


def require(node: Tag, selector: str) -> Tag:
    """Return a required child or report the changed source structure."""
    child = node.select_one(selector)
    if child is None:
        raise UpstreamSchemaError(f"Missing required selector {selector!r}")
    return child


class Document:
    """An immutable source body with mutable extraction diagnostics."""

    def __init__(self, html: str, url: str, fetched_at: datetime) -> None:
        self.soup = BeautifulSoup(html, "lxml")
        self.url = url
        self.fetched_at = fetched_at
        self.html = html
        self.diagnostics: list[Diagnostic] = []
        self.records = inline_records(self.soup)
        self.used_embedded = False

    def root(self, selector: str) -> Tag:
        """Locate a semantic section even inside hidden streaming containers."""
        return require(self.soup, selector)

    def catalog(self, key: str, required_keys: set[str]) -> list[dict[str, Any]] | None:
        """Extract optional inline catalog metadata and record fallback completeness."""
        result = collection(self.records, key, required_keys)
        if result is None:
            self.diagnostics.append(
                Diagnostic(
                    code="embedded_unavailable",
                    message=f"Inline {key} metadata unavailable; using DOM fields.",
                )
            )
        else:
            self.used_embedded = True
        return result

    def source(self) -> SourceInfo:
        """Describe the source document without substituting a missing update date."""
        updated_on = None
        for label in self.soup.find_all(string=re.compile(r"Last updated:")):
            match = re.search(r"(\d{1,2}/[A-Za-z]+/\d{4})", text(label.parent))
            if match:
                try:
                    updated_on = datetime.strptime(match[1], "%d/%B/%Y").date()
                except ValueError:
                    self.diagnostics.append(Diagnostic(code="invalid_update_date", message=match[1]))
                break
        return SourceInfo(
            url=HttpUrl(self.url),
            fetched_at=self.fetched_at,
            updated_on=updated_on,
            content_sha256=hashlib.sha256(self.html.encode("utf-8")).hexdigest(),
            extraction="dom+embedded" if self.used_embedded else "dom",
        )
