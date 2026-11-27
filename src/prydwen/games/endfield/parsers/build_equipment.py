"""Parse ranked equipment, alternatives, potentials, and skill priority displays."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Literal, cast

from bs4 import Tag

from prydwen.exceptions import UpstreamSchemaError
from prydwen.parsing.document import classes, require, text

from ..models.builds import (
    BuildPerformance,
    GearAlternative,
    GearPieceComparison,
    GearRecommendation,
    PotentialRecommendation,
    SkillPriority,
    WeaponRecommendation,
)
from .build_common import BuildContext, guide_blocks


def percentage(value: str) -> Decimal | None:
    """Read a displayed percentage without converting missing comparisons into zero."""
    cleaned = re.sub(r"[\s,%]", "", value)
    if not cleaned:
        return None
    try:
        result = Decimal(cleaned)
    except InvalidOperation as error:
        raise UpstreamSchemaError(f"Invalid build percentage: {value!r}") from error
    if not result.is_finite() or result < 0:
        raise UpstreamSchemaError(f"Invalid build percentage: {value!r}")
    return result


def performance(node: Tag) -> BuildPerformance:
    """Read independently labeled solo/team comparisons from one displayed row."""
    values: dict[str, Decimal | None] = {}
    for rating in node.select(".number.rating"):
        label = text(rating).casefold()
        key = (
            "solo_percent"
            if label.startswith("solo")
            else "team_percent"
            if label.startswith("team")
            else None
        )
        if key:
            values[key] = percentage(text(require(rating, "span")))
    return BuildPerformance(**values)


def rows(nodes: list[Tag]) -> list[Tag]:
    """Find ranked rows without including nested gear pieces or accordion content."""
    return [row for node in nodes for row in node.select(".build-setup > .single-row")]


def row_comment(row: Tag) -> Tag | None:
    """Find the comment belonging to this row before the next recommendation starts."""
    sibling = row.find_next_sibling()
    return sibling if isinstance(sibling, Tag) and "comments" in classes(sibling) else None


def ordinal(row: Tag) -> int:
    """Read the displayed rank or potential number instead of inventing an ordering."""
    match = re.search(r"\d+", text(require(row, ".number:not(.rating)")))
    if match is None:
        raise UpstreamSchemaError("Missing recommendation rank")
    return int(match[0])


def parse_weapon_recommendations(nodes: list[Tag], context: BuildContext) -> list[WeaponRecommendation]:
    """Preserve every ranked weapon, potential level, comparison, and explanation."""
    result = []
    records = list(context.properties.get("weaponRecs") or [])
    for row in rows(nodes):
        weapon = context.equipment(require(row, ".sets"), "weapon")
        potential_match = re.search(r"P\s*(\d+)", text(row.select_one(".cone-super")))
        potential = int(potential_match[1]) if potential_match else None
        comparisons = performance(row)
        matches = [
            record
            for record in records
            if record["Weapon"] == weapon.name and (potential is None or record["Dupes"] == potential)
        ]
        if len(matches) > 1:
            exact = [
                record
                for record in matches
                if percentage(record.get("Percentage_top", "")) == comparisons.solo_percent
                and percentage(record.get("Percentage_bottom", "")) == comparisons.team_percent
            ]
            matches = exact or matches
        record = matches[0] if matches else None
        if record:
            records.remove(record)
        comment = row_comment(row)
        result.append(
            WeaponRecommendation(
                rank=ordinal(row),
                weapon=weapon,
                potential=potential,
                archetype=record.get("Archetype") if record else None,
                performance=comparisons,
                explanation=guide_blocks(comment.children, context.document) if comment is not None else [],
            )
        )
    if context.properties and len(result) != len(context.properties.get("weaponRecs") or []):
        raise UpstreamSchemaError("Weapon recommendation DOM/metadata counts disagree")
    return result


def parse_gear_recommendations(nodes: list[Tag], context: BuildContext) -> list[GearRecommendation]:
    """Parse full loadouts and keep replacement groups and repeated kit slots intact."""
    result = []
    for row in rows(nodes):
        sets = require(row, ".sets")
        empty = sets.select_one(".empty-set")
        gear_set = context.equipment(sets, "gear_set") if empty is None else None
        comment = row_comment(row)
        pieces = []
        alternatives = []
        explanation_nodes = []
        if comment is not None:
            for column in comment.select(".gear-pieces > .column"):
                piece = context.equipment(require(column, ".endfield-gear-icon"), "gear")
                slot = text(column.select_one(".gear-type"))
                pieces.append(piece.model_copy(update={"slot": slot or piece.slot}))
            for item in comment.select(":scope > ul > li"):
                references = item.select(".endfield-gear-inline, .endfield-gear-icon")
                if references:
                    alternatives.append(
                        GearAlternative(
                            pieces=[
                                context.equipment(reference, "gear", name.strip())
                                for reference in references
                                for name in text(require(reference, ".weapon-name")).split(",")
                                if name.strip()
                            ],
                            explanation=guide_blocks(item.children, context.document),
                        )
                    )
                else:
                    explanation_nodes.append(item)
            for child in comment.find_all(recursive=False):
                if child.name == "h6" and text(child).casefold() == "pieces":
                    break
                if child.name != "h6":
                    explanation_nodes.append(child)
        result.append(
            GearRecommendation(
                rank=ordinal(row),
                name=gear_set.name if gear_set else text(empty),
                gear_set=gear_set,
                performance=performance(row),
                pieces=pieces,
                alternatives=alternatives,
                explanation=guide_blocks(explanation_nodes, context.document),
            )
        )
    if context.properties and len(result) != len(context.properties.get("gearSetRecs") or []):
        raise UpstreamSchemaError("Gear recommendation DOM/metadata counts disagree")
    return result


def parse_piece_comparisons(nodes: list[Tag], context: BuildContext) -> list[GearPieceComparison]:
    """Read every slot comparison, its disclaimer marker, and the unequipped baseline."""
    result = []
    for node in nodes:
        for column in node.select(".equipment-table > .single-column"):
            slot = text(require(column, ".top-section"))
            for entry in column.select(".single-gear"):
                reference = entry.select_one(".endfield-gear-inline, .endfield-gear-icon")
                piece = context.equipment(reference, "gear") if reference is not None else None
                label_node = reference if reference is not None else entry.select_one(".empty-gear")
                label = piece.name if piece else text(label_node) or text(entry)
                result.append(
                    GearPieceComparison(
                        slot=slot,
                        piece=piece,
                        label=label,
                        performance=performance(entry),
                        has_disclaimer=reference is not None
                        and any(text(mark) == "*" for mark in reference.select("strong")),
                    )
                )
    return result


def parse_potentials(nodes: list[Tag], context: BuildContext) -> list[PotentialRecommendation]:
    """Read cumulative potential comparisons and each upgrade's explanatory text."""
    result = []
    for row in rows(nodes):
        comment = row_comment(row)
        result.append(
            PotentialRecommendation(
                potential=ordinal(row),
                name=text(require(row, ".sets .name")),
                performance=performance(row),
                explanation=guide_blocks(comment.children, context.document) if comment is not None else [],
            )
        )
    return result


def parse_skill_priorities(nodes: list[Tag], context: BuildContext) -> list[SkillPriority]:
    """Retain every archetype and distinguish equality from strict or weak priority."""
    result = []
    archetype = ""
    for node in nodes:
        if node.name == "h6":
            archetype = text(node).rstrip(" :")
        elif "skill-order" in classes(node):
            raw = node.get_text("", strip=True)
            terms = re.split(r"(>=|>|=)", raw)
            skills = [term.strip() for term in terms[::2]]
            operators = [cast(Literal[">", ">=", "="], term.strip()) for term in terms[1::2]]
            if not archetype or not all(skills) or len(skills) != len(operators) + 1:
                raise UpstreamSchemaError("Invalid skill priority expression")
            following = []
            for sibling in node.find_next_siblings():
                if not isinstance(sibling, Tag):
                    continue
                if sibling.name == "h6" or "skill-order" in classes(sibling):
                    break
                following.append(sibling)
            result.append(
                SkillPriority(
                    archetype=archetype,
                    expression=" ".join(term.strip() for term in terms),
                    skills=skills,
                    operators=operators,
                    explanation=guide_blocks(following, context.document),
                )
            )
    if context.properties and len(result) != len(context.properties.get("skillOrders") or []):
        raise UpstreamSchemaError("Skill priority DOM/metadata counts disagree")
    return result
