"""Decode the supported JSON subset of Next.js inline frames without execution."""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup


def inline_records(soup: BeautifulSoup) -> list[Any]:
    """Join literal text frames and decode only complete JSON Flight records."""
    chunks: list[str] = []
    prefix = "self.__next_f.push("
    decoder = json.JSONDecoder()
    for script in soup.find_all("script"):
        source = script.get_text().strip()
        if not source.startswith(prefix):
            continue
        try:
            frame, _ = decoder.raw_decode(source[len(prefix) :])
        except (ValueError, RecursionError):
            continue
        if isinstance(frame, list) and len(frame) == 2 and frame[0] == 1 and isinstance(frame[1], str):
            chunks.append(frame[1])
    stream = "".join(chunks)
    if len(stream) > 8_000_000:
        return []
    records: list[Any] = []
    for line in stream.splitlines()[:50_000]:
        match = re.match(r"^[0-9a-f]+:", line)
        if match is None:
            continue
        try:
            records.append(json.loads(line[match.end() :]))
        except (ValueError, RecursionError):
            continue
    return records


def collection(records: list[Any], key: str, required_keys: set[str]) -> list[dict[str, Any]] | None:
    """Find a named array with the expected record shape within bounded JSON."""
    pending = [(record, 0) for record in records]
    visited = 0
    while pending and visited < 100_000:
        value, depth = pending.pop()
        visited += 1
        if depth > 60:
            continue
        if isinstance(value, dict):
            candidate = value.get(key)
            if isinstance(candidate, list) and all(
                isinstance(item, dict) and required_keys <= item.keys() for item in candidate
            ):
                return candidate
            pending.extend((child, depth + 1) for child in value.values() if isinstance(child, (dict, list)))
        elif isinstance(value, list):
            pending.extend((child, depth + 1) for child in value if isinstance(child, (dict, list)))
    return None
