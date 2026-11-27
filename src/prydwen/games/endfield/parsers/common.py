"""Endfield identities, displayed stats, and catalog joins."""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit

from bs4 import Tag
from pydantic import HttpUrl

from prydwen.core.models import Diagnostic, EntityAssets
from prydwen.exceptions import UpstreamSchemaError
from prydwen.parsing.assets import absolute_url, image
from prydwen.parsing.document import Document, attr, classes, require, text
from prydwen.parsing.text import slug

from ..models.common import CharacterRef
from ..models.stats import BoostRank, StatUnit, StatValue

STAT_IDS = {
    "hp": 1,
    "atk": 2,
    "attack": 2,
    "def": 3,
    "defense": 3,
    "critical rate": 9,
    "critical damage": 10,
    "strength": 39,
    "agility": 40,
    "intellect": 41,
    "will": 42,
    "ultimate gain efficiency": 44,
    "physical dmg": 50,
    "heat dmg": 51,
    "electric dmg": 52,
    "cryo dmg": 53,
    "nature dmg": 54,
    "ether dmg": 55,
    "arts intensity": 87,
}


def rarity(node: Tag) -> int | None:
    """Read a published rarity class only where the game context establishes it."""
    for label in classes(node):
        match = re.fullmatch(r"rarity-(\d+)", label)
        if match:
            return int(match[1])
    return None


def character_ref(node: Tag, document: Document) -> CharacterRef:
    """Extract a character's actual anchor, name, rarity, and portrait."""
    anchor = node if node.name == "a" else require(node, 'a[href*="/arknights-endfield/characters/"]')
    url = absolute_url(attr(anchor, "href"), document.url)
    avatar = require(anchor, ".avatar")
    portrait = image(avatar.select_one("img"), document.url)
    name = text(anchor.select_one(".emp-name")) or (portrait.alt if portrait else None)
    if not url or not name:
        raise UpstreamSchemaError("Character identity is missing an actual URL or name")
    identifier = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    element_image = avatar.select_one(".element img")
    element_asset = image(element_image, document.url)
    extras = [element_asset] if element_asset is not None else []
    assets = (
        EntityAssets(card=portrait, additional=extras)
        if node.select_one(".emp-name")
        else EntityAssets(icon=portrait, additional=extras)
    )
    return CharacterRef(
        identifier=identifier,
        name=name,
        page_url=HttpUrl(url),
        rarity=rarity(avatar),
        element=attr(element_image, "alt"),
        assets=assets,
    )


def stat(label: str, raw: str) -> StatValue:
    """Normalize a displayed stat without interpreting unknown prose as a formula."""
    cleaned = re.sub(r"[\s,+]", "", raw).replace("\u2212", "-")
    unit = StatUnit.FLAT
    if cleaned.endswith("%"):
        unit = StatUnit.FRACTION
        cleaned = cleaned[:-1]
    elif cleaned.endswith(("\u00d7", "x")):
        unit = StatUnit.FACTOR
        cleaned = cleaned[:-1]
    places = len(cleaned.split(".", 1)[1]) if "." in cleaned else 0
    value: Decimal | None
    try:
        value = Decimal(cleaned)
        if not value.is_finite():
            value = None
        elif unit is StatUnit.FRACTION:
            value /= 100
    except InvalidOperation:
        value = None
    normalized_label = " ".join(label.casefold().split())
    target = {"main attribute": "main_attribute", "secondary attribute": "secondary_attribute"}.get(
        normalized_label, "property"
    )
    return StatValue(
        key=slug(label),
        label=label,
        value=value,
        unit=unit,
        raw_value=raw,
        stat_id=STAT_IDS.get(normalized_label),
        target=target,
        decimal_places=min(places, 12),
    )


def boost_rank(value: str) -> BoostRank | None:
    """Read the current and maximum rank from a stat/passive heading."""
    match = re.search(r"(\d+)\s*/\s*(\d+)", value)
    return BoostRank(current=int(match[1]), maximum=int(match[2])) if match else None


def match_catalog(
    node: Tag, records: list[dict[str, Any]] | None, name: str, document: Document
) -> dict[str, Any] | None:
    """Join catalog enrichment by observed image and name, rejecting ambiguous identities."""
    if records is None:
        return None
    icon = image(node.select_one(".endfield-image img"), document.url)
    matches = [
        record
        for record in records
        if record.get("Name") == name and icon and record.get("image") == str(icon.url)
    ]
    if len(matches) != 1:
        raise UpstreamSchemaError(f"Cannot uniquely join catalog record {name!r}")
    return matches[0]


def local_identity(node: Tag, document: Document, name: str) -> str:
    """Create a marked local key from observed image identity for DOM-only fallback."""
    icon = image(node.select_one(".endfield-image img"), document.url)
    identity = repr((name, str(icon.url) if icon else None))
    return "local-" + hashlib.sha256(identity.encode()).hexdigest()[:16]


def check_count(nodes: list[Tag], records: list[dict[str, Any]] | None, resource: str) -> None:
    """Reject catalogs that silently lose records or have no established empty state."""
    if not nodes:
        raise UpstreamSchemaError(f"No {resource} records found in the expected section")
    if records is not None and len(nodes) != len(records):
        raise UpstreamSchemaError(f"{resource} DOM/inline record counts disagree")


def ensure_unique(identifiers: list[str], resource: str) -> None:
    """Reject identity collisions rather than overwrite distinct source records."""
    if len(set(identifiers)) != len(identifiers):
        raise UpstreamSchemaError(f"Duplicate identifiers in {resource}")


def unknown_stats(values: list[StatValue], document: Document, identifier: str) -> None:
    """Attach diagnostics for values and labels outside the established stat mapping."""
    for value in values:
        if value.value is None or (value.stat_id is None and value.target == "property"):
            document.diagnostics.append(
                Diagnostic(
                    code="unmapped_stat",
                    record_key=identifier,
                    field_path=value.key,
                    message=f"Preserved source stat {value.label}: {value.raw_value}",
                )
            )
