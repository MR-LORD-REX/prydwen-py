"""Shared identity and structured-prose extraction for character guide sections."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any, Literal
from urllib.parse import urlsplit

from bs4 import Comment, Tag
from bs4.element import PageElement
from pydantic import HttpUrl

from prydwen.core.models import Diagnostic, EntityAssets
from prydwen.exceptions import UpstreamSchemaError
from prydwen.parsing.assets import absolute_url, asset, image
from prydwen.parsing.document import Document, attr, classes, text
from prydwen.parsing.embedded import collection
from prydwen.parsing.text import plain_html, slug

from ..models.builds import EquipmentRef, GuideBlock, GuideLink
from ..models.common import CharacterRef
from .common import character_ref, rarity, stat


def build_properties(document: Document) -> dict[str, Any] | None:
    """Find guide properties by shape and page slug without depending on Flight record IDs."""
    identifier = urlsplit(document.url).path.rstrip("/").rsplit("/", 1)[-1]
    pending = [(record, 0) for record in document.records]
    visited = 0
    while pending and visited < 100_000:
        value, depth = pending.pop()
        visited += 1
        if depth > 60:
            continue
        if isinstance(value, dict):
            if {"character", "weaponRecs", "teamRotations"} <= value.keys():
                character = value["character"]
                if not isinstance(character, dict) or character.get("slug") != identifier:
                    raise UpstreamSchemaError("Character guide metadata does not match the requested page")
                document.used_embedded = True
                return value
            pending.extend((child, depth + 1) for child in value.values() if isinstance(child, (dict, list)))
        elif isinstance(value, list):
            pending.extend((child, depth + 1) for child in value if isinstance(child, (dict, list)))
    document.diagnostics.append(
        Diagnostic(
            code="build_metadata_unavailable",
            message="Using rendered guide sections; embedded chart data and some identities may be unavailable.",
        )
    )
    return None


class BuildContext:
    """Resolve observed guide references against the catalogs embedded in that same HTML."""

    def __init__(self, document: Document, properties: dict[str, Any] | None) -> None:
        self.document = document
        self.properties = properties or {}
        self.characters = collection(document.records, "characters", {"slug", "name", "smallImage"}) or []
        self.equipment_records = {
            "weapon": collection(document.records, "weapons", {"Name", "Slug", "image"}) or [],
            "gear": collection(document.records, "gearPieces", {"Name", "Slug", "image"}) or [],
            "gear_set": collection(document.records, "gearSets", {"Name", "Code"}) or [],
        }

    def character(self, identifier: str) -> CharacterRef | None:
        """Resolve an explicit source slug, retaining its actual published asset URLs."""
        record = next((entry for entry in self.characters if entry["slug"] == identifier), None)
        if record is not None:
            return CharacterRef(
                identifier=identifier,
                name=record["name"],
                page_url=HttpUrl(f"https://www.prydwen.gg/arknights-endfield/characters/{identifier}"),
                source_id=record.get("id"),
                source_unit_id=record.get("unitId"),
                rarity=int(record["rarity"]) if record.get("rarity") else None,
                element=record.get("element"),
                operator_class=record.get("class"),
                weapon_type=record.get("weapon"),
                assets=EntityAssets(
                    icon=asset(record.get("smallImage"), self.document.url, record["name"]),
                    card=asset(record.get("cardImage"), self.document.url, record["name"]),
                ),
            )
        for anchor in self.document.soup.select('a[href*="/arknights-endfield/characters/"]'):
            if (attr(anchor, "href") or "").rstrip("/").rsplit("/", 1)[-1] == identifier:
                return character_ref(anchor, self.document)
        return None

    def actor(self, node: Tag) -> CharacterRef | None:
        """Resolve a linked actor or a timeline portrait through observed catalog identity."""
        anchor = node if node.name == "a" else node.select_one('a[href*="/characters/"]')
        if anchor is not None:
            identifier = (attr(anchor, "href") or "").rstrip("/").rsplit("/", 1)[-1]
            return self.character(identifier) or character_ref(anchor, self.document)
        portrait = image(node.select_one("img"), self.document.url)
        if portrait is not None:
            matches = [
                record
                for record in self.characters
                if record["name"] == portrait.alt and record["smallImage"] == str(portrait.url)
            ]
            if len(matches) == 1:
                return self.character(matches[0]["slug"])
        return None

    def equipment(
        self, node: Tag, kind: Literal["weapon", "gear", "gear_set"], name_override: str | None = None
    ) -> EquipmentRef:
        """Join an equipment name and image without collapsing same-named catalog pieces."""
        name_node = node.select_one(".weapon-name, .name")
        name = name_override or (text(name_node) if name_node is not None else text(node))
        icon = image(node.select_one("img"), self.document.url)
        candidates = [record for record in self.equipment_records[kind] if record["Name"] == name]
        if kind != "gear_set" and icon is not None:
            candidates = [record for record in candidates if record["image"] == str(icon.url)]
        record = candidates[0] if len(candidates) == 1 else None
        if not name:
            raise UpstreamSchemaError("Missing equipment recommendation name")
        if record is None:
            self.document.diagnostics.append(
                Diagnostic(
                    code="unresolved_build_equipment",
                    message=f"No unique {kind} catalog match for {name}",
                    record_key=name,
                )
            )
        icon_node = node.select_one(".endfield-image")
        stats = []
        if record:
            for index in range(1, 5):
                label, value = record.get(f"Stat_{index}_Type"), record.get(f"Stat_{index}")
                if label and value:
                    stats.append(stat(str(label), str(value)))
        return EquipmentRef(
            kind=kind,
            identifier=(slug(name) if kind == "gear_set" else record["Slug"]) if record else None,
            source_id=record.get("ID") if record else None,
            name=name,
            rarity=(
                int(record["Rarity"])
                if record and record.get("Rarity")
                else rarity(icon_node)
                if icon_node is not None and kind == "weapon"
                else None
            ),
            slot=record.get("Type") if record and kind == "gear" else None,
            set_name=record.get("Set") if record and kind == "gear" else None,
            weapon_type=record.get("Type") if record and kind == "weapon" else None,
            base_attack=record.get("ATK") if record and kind == "weapon" else None,
            defense=record.get("Def") if record and kind == "gear" else None,
            stats=stats,
            passive=plain_html(record["Passive"]) if record and record.get("Passive") else None,
            assets=EntityAssets(
                icon=icon or asset(record.get("image"), self.document.url, name) if record else icon
            ),
        )


def section_nodes(tab: Tag) -> dict[str, list[Tag]]:
    """Group direct tab children by semantic content headings, including preamble notes."""
    result: dict[str, list[Tag]] = {"preamble": []}
    current = "preamble"
    for child in tab.find_all(recursive=False):
        if "mobile-header" in classes(child):
            continue
        if "content-header" in classes(child):
            current = text(child).casefold()
            if current in result:
                raise UpstreamSchemaError(f"Duplicate guide section {current!r}")
            result[current] = []
        else:
            result[current].append(child)
    return result


def guide_links(node: Tag, document: Document) -> list[GuideLink]:
    """Preserve ordinary web links while rejecting executable and inline schemes."""
    result = []
    for anchor in node.select("a[href]"):
        url = absolute_url(attr(anchor, "href"), document.url)
        if url:
            result.append(GuideLink(text=text(anchor), url=HttpUrl(url)))
    return result


def guide_highlights(node: Tag) -> list[str]:
    """Preserve all explicitly emphasized phrases for concise text and card rendering."""
    return list(dict.fromkeys(text(item) for item in node.select("strong,b,em,mark,u") if text(item)))


def guide_blocks(
    nodes: Iterable[PageElement],
    document: Document,
    rotation_handler: Callable[[Tag], GuideBlock] | None = None,
) -> list[GuideBlock]:
    """Convert source prose to ordered display blocks without returning executable HTML."""
    blocks: list[GuideBlock] = []
    for node in nodes:
        if isinstance(node, Comment):
            continue
        if not isinstance(node, Tag):
            value = " ".join(str(node).split())
            if value:
                blocks.append(GuideBlock(kind="paragraph", text=value))
            continue
        labels = classes(node)
        if node.name in {"script", "style", "template", "svg"}:
            continue
        is_rotation = (
            "ake-team-rotations-builder-embed" in labels or "team-setup" in labels and "combo" in labels
        )
        if is_rotation:
            if rotation_handler is not None:
                blocks.append(rotation_handler(node))
            elif "combo" in labels:
                items = []
                for step in node.select(":scope > .single:not(.order)"):
                    portrait = step.select_one("img")
                    actor = attr(portrait, "alt") if portrait else None
                    items.append(f"{actor}: {text(step)}" if actor else text(step))
                blocks.append(GuideBlock(kind="list", ordered=True, items=items))
            continue
        if "yt-facade" in labels:
            thumbnail = image(node.select_one("img"), document.url)
            match = (
                re.search(r"/(?:vi|vi_webp)/([A-Za-z0-9_-]{11})/", str(thumbnail.url)) if thumbnail else None
            )
            blocks.append(
                GuideBlock(
                    kind="video",
                    image=thumbnail,
                    video_id=match[1] if match else None,
                    media_url=HttpUrl(f"https://www.youtube.com/watch?v={match[1]}") if match else None,
                )
            )
        elif node.name == "iframe":
            url = absolute_url(attr(node, "src"), document.url)
            if url:
                blocks.append(GuideBlock(kind="video", media_url=HttpUrl(url)))
        elif node.name == "img":
            picture = image(node, document.url)
            if picture:
                blocks.append(GuideBlock(kind="image", image=picture))
        elif node.name in {"ul", "ol"}:
            items = []
            children = []
            for item in node.find_all("li", recursive=False):
                own = [
                    child
                    for child in item.children
                    if not isinstance(child, Tag) or child.name not in {"ul", "ol"}
                ]
                items.append(
                    " ".join(
                        text(child) if isinstance(child, Tag) else str(child).strip() for child in own
                    ).strip()
                )
                children.extend(guide_blocks(item.find_all(["ul", "ol"], recursive=False), document))
            blocks.append(
                GuideBlock(
                    kind="list",
                    ordered=node.name == "ol",
                    items=items,
                    children=children,
                    links=guide_links(node, document),
                    highlights=guide_highlights(node),
                )
            )
        elif node.name == "table":
            rows = [
                [text(cell) for cell in row.find_all(["th", "td"], recursive=False)]
                for row in node.select("tr")
            ]
            blocks.append(GuideBlock(kind="table", rows=rows, links=guide_links(node, document)))
        elif re.fullmatch(r"h[1-6]", node.name):
            blocks.append(
                GuideBlock(
                    kind="heading",
                    level=int(node.name[1]),
                    text=text(node),
                    links=guide_links(node, document),
                    highlights=guide_highlights(node),
                )
            )
        elif node.name in {"p", "blockquote"} or any(label in labels for label in ("callout", "info-box")):
            if text(node):
                blocks.append(
                    GuideBlock(
                        kind="callout"
                        if node.name == "blockquote" or "callout" in labels or "info-box" in labels
                        else "paragraph",
                        text=text(node),
                        links=guide_links(node, document),
                        highlights=guide_highlights(node),
                    )
                )
        else:
            blocks.extend(guide_blocks(node.children, document, rotation_handler))
    return blocks
