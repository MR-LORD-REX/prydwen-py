"""Plain rich text and explicit numeric parsing."""

from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup, NavigableString, Tag


def plain_html(value: str) -> str:
    """Convert untrusted descriptive HTML into safe text with block boundaries."""
    soup = BeautifulSoup(value, "lxml")
    for node in soup.select("script,style,iframe"):
        node.decompose()
    for node in soup.select("br"):
        node.replace_with(NavigableString("\n"))
    for node in soup.select("p,li"):
        node.append("\n")
    return "\n".join(" ".join(line.split()) for line in soup.get_text().splitlines() if line.strip())


def integer(value: str) -> int:
    """Parse an integer with visible separators and an optional leading plus."""
    normalized = re.sub(r"[\s,+\u00d7\u2726]", "", value)
    return int(normalized)


def aware_time(value: str | None) -> datetime | None:
    """Decode an explicit ISO timestamp without inventing a timezone."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def slug(value: str) -> str:
    """Build a local readable key without claiming it is an upstream ID."""
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def label_values(node: Tag) -> dict[str, str]:
    """Read labeled header values without relying on their displayed order."""
    result = {}
    for paragraph in node.select(".endfield-info > p"):
        label = paragraph.get_text(" ", strip=True).split(":", 1)[0]
        strong = paragraph.select_one("strong")
        if strong is not None:
            result[label.strip()] = strong.get_text("", strip=True)
    return result
