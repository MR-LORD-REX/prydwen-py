"""Parse distinct gear identities, displayed attributes, and set memberships."""

import re

from prydwen.core.models import EntityAssets
from prydwen.exceptions import UpstreamSchemaError
from prydwen.parsing.assets import image
from prydwen.parsing.document import Document, require, text
from prydwen.parsing.text import integer, label_values, plain_html, slug

from ..models.gear import AllGear, Gear, GearSet, GearSetBonus
from .common import check_count, ensure_unique, local_identity, match_catalog, stat, unknown_stats


def parse_gear(document: Document) -> AllGear:
    """Extract pieces and set bonuses without merging items with equal names."""
    root = document.root(".endfield-gear-container")
    nodes = root.select(".endfield-gear-box")
    records = document.catalog("gear", {"ID", "Slug", "Name", "Def"})
    set_records = document.catalog("gearSets", {"Name", "Code", "Passive"})
    check_count(nodes, records, "gear")
    sets_by_name = {record["Name"]: record for record in set_records or []}
    ensure_unique(list(record["Name"] for record in set_records or []), "gear set names")
    gears = []
    set_details: dict[str, GearSet] = {}
    for node in nodes:
        name = text(require(node, "h4"))
        record = match_catalog(node, records, name, document)
        identifier = record["Slug"] if record else local_identity(node, document, name)
        labels = label_values(node)
        stats = [
            stat(
                text(require(row, ".left")).rstrip(":").strip(),
                require(row, ".right").get_text("", strip=True),
            )
            for row in node.select(".stat-group > div")
        ]
        set_name = text(node.select_one(".set-pill"))
        set_identifier = None
        if set_name:
            source_set = sets_by_name.get(set_name)
            set_identifier = slug(source_set["Code"] if source_set else set_name)
            if set_identifier not in set_details:
                bonus_heading = next(
                    (text(heading) for heading in node.select("h6") if "Gear Set" in text(heading)), ""
                )
                piece_match = re.search(r"(\d+)-PC", bonus_heading)
                passive = (
                    source_set["Passive"]
                    if source_set
                    else str(node.select_one(".set-description .skill-with-coloring") or "")
                )
                bonus_stats = []
                if source_set and source_set.get("Stat_1_Type") and source_set.get("Stat_1"):
                    bonus_stats.append(stat(source_set["Stat_1_Type"], source_set["Stat_1"]))
                if piece_match is None:
                    raise UpstreamSchemaError(f"Missing piece-count requirement for {set_name}")
                set_details[set_identifier] = GearSet(
                    identifier=set_identifier,
                    name=set_name,
                    source_code=source_set["Code"] if source_set else None,
                    bonuses=[
                        GearSetBonus(
                            required_pieces=int(piece_match[1]),
                            stats=bonus_stats,
                            passive=plain_html(passive),
                        )
                    ],
                    gears=[],
                )
        unknown_stats(stats, document, identifier)
        gears.append(
            Gear(
                identifier=identifier,
                source_id=record["ID"] if record else None,
                name=name,
                slot=labels["Type"],
                level=integer(labels["Level"]) if "Level" in labels else None,
                defense=integer(labels["DEF"]),
                stats=stats,
                set_identifier=set_identifier,
                assets=EntityAssets(icon=image(node.select_one(".endfield-image img"), document.url)),
            )
        )
    ensure_unique([piece.identifier for piece in gears], "gear")
    if set_records is not None and {record["Name"] for record in set_records} != {
        gear_set.name for gear_set in set_details.values()
    }:
        raise UpstreamSchemaError("Gear set metadata and displayed memberships disagree")
    sets = [
        gear_set.model_copy(
            update={"gears": [piece for piece in gears if piece.set_identifier == identifier]}
        )
        for identifier, gear_set in set_details.items()
    ]
    return AllGear(source=document.source(), diagnostics=document.diagnostics, gears=gears, gear_sets=sets)
