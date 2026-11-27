"""Parse displayed weapon stats and passive boost ranks."""

from prydwen.core.models import EntityAssets
from prydwen.parsing.assets import image
from prydwen.parsing.document import Document, require, text
from prydwen.parsing.text import integer, label_values, plain_html

from ..models.stats import StatBoost
from ..models.weapons import AllWeapons, Weapon
from .common import (
    boost_rank,
    check_count,
    ensure_unique,
    local_identity,
    match_catalog,
    stat,
    unknown_stats,
)


def parse_weapons(document: Document) -> AllWeapons:
    """Extract weapon records and keep the exact stat/passive display context."""
    root = document.root(".endfield-weapons-container")
    nodes = root.select(".endfield-weapon-box")
    records = document.catalog("weapons", {"ID", "Slug", "Name", "ATK"})
    check_count(nodes, records, "weapons")
    weapons = []
    for node in nodes:
        name = text(require(node, "h4"))
        record = match_catalog(node, records, name, document)
        labels = label_values(node)
        identifier = record["Slug"] if record else local_identity(node, document, name)
        boosts: list[StatBoost] = []
        passive_rank = None
        passive = ""
        for box in node.select(".stat-box"):
            heading = text(require(box, ".title"))
            if heading.startswith("Passive Boost"):
                passive_rank = boost_rank(heading)
                passive = plain_html(str(require(box, ".combined")))
            else:
                paragraph = require(box, "p.normal")
                label = text(paragraph).split(":", 1)[0].strip()
                raw = require(paragraph, "strong").get_text("", strip=True)
                boosts.append(
                    StatBoost(
                        slot=len(boosts) + 1,
                        stat=stat(label, raw),
                        rank=boost_rank(heading),
                    )
                )
        unknown_stats([boost.stat for boost in boosts], document, identifier)
        weapons.append(
            Weapon(
                identifier=identifier,
                source_id=record["ID"] if record else None,
                name=name,
                weapon_type=labels["Type"],
                rarity=integer(labels["Rarity"]),
                base_attack=integer(labels["Base ATK"]),
                stat_boosts=boosts,
                passive=passive,
                passive_rank=passive_rank,
                assets=EntityAssets(icon=image(node.select_one(".endfield-image img"), document.url)),
            )
        )
    ensure_unique([weapon.identifier for weapon in weapons], "weapons")
    return AllWeapons(source=document.source(), diagnostics=document.diagnostics, weapons=weapons)
