"""Parse an entire character build guide using semantic sections and inline chart data."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from bs4 import Tag
from pydantic import HttpUrl

from prydwen.core.models import Diagnostic, EntityAssets
from prydwen.exceptions import UpstreamSchemaError
from prydwen.parsing.assets import asset, image
from prydwen.parsing.document import Document, classes, require, text

from ..models.builds import (
    BuildCalculations,
    BuildRating,
    BuildUpdates,
    CalculationMember,
    CharacterBuild,
    CharacterReview,
    DamageContribution,
    DamageDistribution,
    SectionAvailability,
)
from ..models.common import CharacterRef
from .build_common import BuildContext, build_properties, guide_blocks, section_nodes
from .build_equipment import (
    parse_gear_recommendations,
    parse_piece_comparisons,
    parse_potentials,
    parse_skill_priorities,
    parse_weapon_recommendations,
    percentage,
)
from .build_teams import parse_build_teams, parse_synergies
from .common import rarity


def owner_reference(root: Tag, context: BuildContext) -> CharacterRef:
    """Validate the page owner and enrich their identity with actual hero/gallery images."""
    document = context.document
    identifier = urlsplit(document.url).path.rstrip("/").rsplit("/", 1)[-1]
    heading = require(root, "h1")
    hero = image(root.select_one(".right-image > img"), document.url)
    owner = context.character(identifier)
    record = context.properties.get("character") or {}
    name = record.get("name") or (hero.alt if hero else None)
    if not name or not text(heading).startswith(name):
        raise UpstreamSchemaError("Character headline and guide identity disagree")
    if owner is None:
        owner = CharacterRef(
            identifier=identifier,
            name=name,
            page_url=HttpUrl(document.url),
            source_id=record.get("id"),
            rarity=int(record["rarity"]) if record.get("rarity") else rarity(heading),
            element=record.get("element"),
            operator_class=record.get("class"),
            weapon_type=record.get("weaponType"),
        )
    if owner.name != name:
        raise UpstreamSchemaError("Character catalog and detail page identities disagree")
    assets = EntityAssets(
        icon=owner.assets.icon or asset(record.get("thumbnailUrl"), document.url, name),
        card=hero or owner.assets.card,
        portrait=image(root.select_one("img.full-image"), document.url),
        additional=owner.assets.additional,
    )
    return owner.model_copy(update={"assets": assets, "page_url": HttpUrl(document.url)})


def parse_review(sections: dict[str, list[Tag]], context: BuildContext) -> CharacterReview:
    """Parse role/form ratings independently from optional review prose and pros/cons."""
    ratings = []
    for section in sections["ratings"]:
        for rating in section.select(".ratings") if "ratings" not in classes(section) else [section]:
            role = text(require(rating, "h6"))
            tags = [
                record.get("tags", "").strip()
                for record in context.properties.get("tierRatings", [])
                if {"DPS": "Damage"}.get(record["category"], record["category"]).casefold() == role.casefold()
            ]
            for box in rating.select(".rating-box-container"):
                ratings.append(
                    BuildRating(
                        role=role,
                        tier=text(require(box, ".rating-box")),
                        mode=text(box.select_one("p")) or None,
                        notes=list(dict.fromkeys(tag for tag in tags if tag)),
                    )
                )
    pros = [text(item) for node in sections["pros & cons"] for item in node.select(".box.pros li")]
    cons = [text(item) for node in sections["pros & cons"] for item in node.select(".box.cons li")]
    review_nodes = [node for node in sections["review"] if "section-analysis" in classes(node)]
    content = [block for node in review_nodes for block in guide_blocks(node.children, context.document)]
    return CharacterReview(ratings=ratings, pros=pros, cons=cons, content=content)


def parse_calculations(nodes: list[Tag], owner: CharacterRef, context: BuildContext) -> BuildCalculations:
    """Recover source pie values and the exact equipment setup used for comparisons."""
    members = []
    chart_nodes: list[Tag] = []
    notes = []
    for node in nodes:
        if "team-calc-overview" in classes(node):
            for column in node.select(":scope > .column"):
                character = context.actor(require(column, ".character"))
                if character is None:
                    raise UpstreamSchemaError("A calculation operator has no identity")
                weapon = column.select_one(".endfield-weapon-icon")
                gear_set = column.select_one(".endfield-set-icon")
                members.append(
                    CalculationMember(
                        character=character,
                        weapon=context.equipment(weapon, "weapon") if weapon else None,
                        gear_set=context.equipment(gear_set, "gear_set") if gear_set else None,
                        pieces=[
                            context.equipment(piece, "gear") for piece in column.select(".endfield-gear-icon")
                        ],
                    )
                )
        elif "team-damage-split" in classes(node):
            chart_nodes.extend(node.select(".split"))
        else:
            notes.extend(guide_blocks([node], context.document))
    charts = []
    for node in chart_nodes:
        contributions = []
        scope: Literal["character", "team"] = "character" if "solo" in classes(node) else "team"
        if scope == "character":
            record = context.properties.get("damageCharacter")
            if isinstance(record, dict):
                for index in range(1, 7):
                    name = record.get(f"Dmg_{index}_Name")
                    if name:
                        value = percentage(str(record[f"Dmg_{index}_Value"]))
                        if value is None:
                            raise UpstreamSchemaError("A named chart slice has no percentage")
                        contributions.append(DamageContribution(label=name, percent=value))
        else:
            records = context.properties.get("teams") or []
            if records:
                record = records[0]
                for index in range(1, 5):
                    identifier = record.get(f"Member_{index}_Name")
                    if identifier:
                        character = context.character(identifier)
                        value = percentage(str(record.get(f"Member_{index}_Perc", "")))
                        if value is not None:
                            contributions.append(
                                DamageContribution(
                                    label=character.name if character else identifier,
                                    percent=value,
                                    character=character,
                                )
                            )
        if not contributions:
            context.document.diagnostics.append(
                Diagnostic(
                    code="chart_data_unavailable",
                    message=f"No data for {text(node.select_one('h6'))}",
                )
            )
            continue
        chart = DamageDistribution(
            title=text(node.select_one("h6")) or f"{owner.name} Damage Split",
            scope=scope,
            contributions=contributions,
        )
        if abs(chart.total_percent - Decimal(100)) > Decimal("0.5"):
            context.document.diagnostics.append(
                Diagnostic(
                    code="chart_total_mismatch",
                    message=f"{chart.title} sums to {chart.total_percent}%.",
                )
            )
        charts.append(chart)
    return BuildCalculations(members=members, charts=charts, notes=notes)


def availability(nodes: list[Tag], populated: bool) -> SectionAvailability:
    """Keep explicit pending/unavailable messages separate from real populated content."""
    if populated:
        return SectionAvailability(status="available")
    message = " ".join(text(node) for node in nodes).strip() or None
    pending = message is not None and bool(
        re.search(r"(?:not|n't) available yet|added soon|coming soon", message, re.I)
    )
    return SectionAvailability(status="pending" if pending else "unavailable", message=message)


def parse_character_build(document: Document, expected_identifier: str | None = None) -> CharacterBuild:
    """Parse review, complete build choices, best teams, charts, and rotation instructions."""
    root = document.root(".character-page.character-ake")
    properties = build_properties(document)
    context = BuildContext(document, properties)
    owner = owner_reference(root, context)
    if expected_identifier is not None and owner.identifier != expected_identifier:
        raise UpstreamSchemaError("The retrieved character guide differs from the requested identifier")
    tabs = {}
    for tab in root.select(":scope > .tab-inside"):
        label = text(require(tab, ":scope > .mobile-header")).casefold()
        tabs[label] = section_nodes(tab)
    if not {"review", "build", "teams and synergies"} <= tabs.keys():
        raise UpstreamSchemaError("Character guide tabs are incomplete")
    review_sections = tabs["review"]
    build_sections = tabs["build"]
    team_sections = tabs["teams and synergies"]
    if (
        not {"ratings", "pros & cons", "review"} <= review_sections.keys()
        or not {
            "best weapons",
            "best gear",
            "best gear pieces",
            "potentials review",
            "calculations",
            "skill priority",
        }
        <= build_sections.keys()
        or not {"synergies", "teams"} <= team_sections.keys()
    ):
        raise UpstreamSchemaError("Character guide sections are incomplete")
    review = parse_review(review_sections, context)
    weapons = parse_weapon_recommendations(build_sections["best weapons"], context)
    gear_sets = parse_gear_recommendations(build_sections["best gear"], context)
    gear_pieces = parse_piece_comparisons(build_sections["best gear pieces"], context)
    potentials = parse_potentials(build_sections["potentials review"], context)
    priorities = parse_skill_priorities(build_sections["skill priority"], context)
    synergies = parse_synergies(team_sections["synergies"], context)
    teams = parse_build_teams(team_sections["teams"], owner, context)
    calculations = parse_calculations(build_sections["calculations"], owner, context)
    last_update = context.properties.get("lastUpdate") or {}
    states = {
        "ratings": availability(review_sections["ratings"], bool(review.ratings)),
        "review": availability(
            review_sections["review"],
            bool((context.properties.get("character") or {}).get("review"))
            if properties
            else bool(review.content),
        ),
        "weapons": availability(build_sections["best weapons"], bool(weapons)),
        "gear_sets": availability(build_sections["best gear"], bool(gear_sets)),
        "gear_pieces": availability(build_sections["best gear pieces"], bool(gear_pieces)),
        "potentials": availability(build_sections["potentials review"], bool(potentials)),
        "skill_priority": availability(build_sections["skill priority"], bool(priorities)),
        "synergies": availability(team_sections["synergies"], bool(synergies)),
        "teams": availability(team_sections["teams"], bool(teams)),
        "calculations": availability(
            build_sections["calculations"], bool(calculations.members or calculations.charts)
        ),
    }
    notes = {}
    for heading, nodes in build_sections.items():
        prose = []
        for node in nodes:
            if any(
                label in classes(node)
                for label in (
                    "build-setup",
                    "equipment-table",
                    "team-calc-overview",
                    "team-damage-split",
                    "skill-order",
                    "dps-comparison",
                )
            ):
                continue
            if heading != "skill priority":
                prose.extend(guide_blocks([node], document))
        if prose:
            notes[heading] = prose
    for heading in ("teams", "synergies"):
        prose = [
            block
            for node in team_sections[heading]
            if "info-box" in classes(node)
            for block in guide_blocks([node], document)
        ]
        if prose:
            notes[heading] = prose
    return CharacterBuild(
        source=document.source(),
        diagnostics=document.diagnostics,
        character=owner,
        availability=states,
        updates=BuildUpdates(
            review_patch=str(last_update["review"]) if last_update.get("review") is not None else None,
            build_patch=str(last_update["build"]) if last_update.get("build") is not None else None,
            teams_patch=str(last_update["synergy"]) if last_update.get("synergy") is not None else None,
        ),
        review=review,
        weapons=weapons,
        gear_sets=gear_sets,
        gear_pieces=gear_pieces,
        potentials=potentials,
        skill_priority=priorities,
        synergies=synergies,
        teams=teams,
        calculations=calculations,
        notes=notes,
    )
