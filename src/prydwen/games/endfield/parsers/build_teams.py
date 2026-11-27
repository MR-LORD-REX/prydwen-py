"""Parse source team rosters and both timed and untimed rotation diagrams."""

from __future__ import annotations

import re
from decimal import Decimal

from bs4 import Tag

from prydwen.core.models import Diagnostic
from prydwen.exceptions import UpstreamSchemaError
from prydwen.parsing.document import attr, classes, require, text

from ..models.builds import (
    BuildTeam,
    CharacterSynergy,
    GuideBlock,
    RotationStep,
    TeamRotation,
    TimelineAction,
    TimelineRow,
)
from ..models.common import CharacterRef
from .build_common import BuildContext, guide_blocks


def css_value(node: Tag, property_name: str) -> str | None:
    """Read a literal CSS property from the source visualization without executing styles."""
    for declaration in (attr(node, "style") or "").split(";"):
        key, separator, value = declaration.partition(":")
        if separator and key.strip().casefold() == property_name:
            return value.strip()
    return None


def pixels(node: Tag, property_name: str) -> Decimal:
    """Read a numeric pixel coordinate, rejecting unsupported or changed geometry."""
    raw = css_value(node, property_name) or ""
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)px", raw)
    if match is None:
        raise UpstreamSchemaError(f"Unsupported rotation {property_name}: {raw!r}")
    return Decimal(match[1])


def rotation_title(node: Tag) -> str | None:
    """Find the nearest preceding heading inside this team's own guide."""
    guide = node.find_parent(class_="team-how-to-play")
    heading = node.find_previous(["h3", "h4", "h5", "h6"])
    return (
        text(heading)
        if isinstance(heading, Tag) and isinstance(guide, Tag) and guide in heading.parents
        else None
    )


def parse_timeline(node: Tag, context: BuildContext) -> TeamRotation:
    """Calibrate displayed pixels against second markers and preserve every actor/action."""
    markers = []
    for marker in node.select(".timeline-second-marker"):
        match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*s", text(marker))
        if match is None:
            raise UpstreamSchemaError("Invalid rotation second marker")
        markers.append((Decimal(match[1]), pixels(marker, "left")))
    if len(markers) < 2:
        raise UpstreamSchemaError("Rotation timeline has no verifiable time scale")
    markers.sort()
    first_time, first_pixel = markers[0]
    second_time, second_pixel = markers[1]
    if second_time <= first_time or second_pixel <= first_pixel:
        raise UpstreamSchemaError("Invalid rotation time scale")
    scale = (second_pixel - first_pixel) / (second_time - first_time)
    origin = first_pixel - first_time * scale
    if any(abs(position - (origin + instant * scale)) > Decimal("0.000001") for instant, position in markers):
        raise UpstreamSchemaError("Rotation marker geometry is inconsistent")
    headers = node.select(".character-column > .character-row-header")
    lanes = node.select(".canvas-timeline > .timeline-row")
    if not headers or len(headers) != len(lanes):
        raise UpstreamSchemaError("Rotation actor and lane counts disagree")
    rows = []
    for header, lane in zip(headers, lanes, strict=True):
        character = context.actor(header)
        label = character.name if character else attr(header.select_one("img"), "alt") or text(header)
        if character is None:
            context.document.diagnostics.append(
                Diagnostic(
                    code="unresolved_rotation_actor",
                    message=f"Kept unlabeled rotation lane: {label}",
                )
            )
        actions = []
        for block in lane.select(":scope > .action-block"):
            actions.append(
                TimelineAction(
                    action=text(require(block, ".action-label")),
                    start_seconds=(pixels(block, "left") - origin) / scale,
                    duration_seconds=pixels(block, "width") / scale,
                    color=css_value(block, "background-color"),
                )
            )
        actions.sort(key=lambda action: action.start_seconds)
        rows.append(TimelineRow(label=label, character=character, actions=actions))
    duration = max([markers[-1][0], *(action.end_seconds for row in rows for action in row.actions)])
    return TeamRotation(
        kind="timeline", title=rotation_title(node), rows=rows, displayed_duration_seconds=duration
    )


def parse_sequence(node: Tag, context: BuildContext) -> TeamRotation:
    """Read ordered instructions while leaving omitted actors and timing unspecified."""
    steps: list[RotationStep] = []
    for entry in node.select(":scope > .single:not(.order)"):
        steps.append(
            RotationStep(
                order=len(steps) + 1,
                character=context.actor(entry),
                action=text(require(entry, "p")),
            )
        )
    if not steps:
        raise UpstreamSchemaError("An empty rotation sequence has no established meaning")
    return TeamRotation(kind="sequence", title=rotation_title(node), steps=steps)


def parse_build_teams(nodes: list[Tag], owner: CharacterRef, context: BuildContext) -> list[BuildTeam]:
    """Keep team-local guides and diagrams, including implicit owners and flexible rosters."""
    result = []
    for section in nodes:
        for node in section.select(".special-team-viewer > .single-team"):
            displayed = []
            for anchor in node.select(".team-members > .team-setup a[href]"):
                character = context.actor(anchor)
                if character is None:
                    raise UpstreamSchemaError("A displayed team member has no character identity")
                displayed.append(character)
            if not displayed:
                raise UpstreamSchemaError("A published team has no members")
            implicit = len(displayed) == 3 and owner.identifier not in {
                member.identifier for member in displayed
            }
            members = [owner, *displayed] if implicit else displayed.copy()
            rotations: list[TeamRotation] = []

            def rotation_block(widget: Tag, team_rotations: list[TeamRotation] = rotations) -> GuideBlock:
                """Keep a diagram's exact position in its team's ordered guide content."""
                rotation = (
                    parse_timeline(widget, context)
                    if "ake-team-rotations-builder-embed" in classes(widget)
                    else parse_sequence(widget, context)
                )
                team_rotations.append(rotation)
                return GuideBlock(kind="rotation", rotation_index=len(team_rotations) - 1)

            guide = node.select_one(".team-how-to-play")
            result.append(
                BuildTeam(
                    name=text(require(node, ".team-name")),
                    members=members,
                    displayed_members=displayed,
                    owner_implicit=implicit,
                    guide=guide_blocks(guide.children, context.document, rotation_block)
                    if guide is not None
                    else [],
                    rotations=rotations,
                )
            )
    records = context.properties.get("teamRotations") or []
    if context.properties and len(result) != len(records):
        raise UpstreamSchemaError("Team guide DOM/metadata counts disagree")
    for team, record in zip(result, records, strict=False):
        expected = sum(
            block.get("type") in {"rotation", "timeline-tool"} for block in (record.get("guide") or [])
        )
        if team.name != record["name"] or expected != len(team.rotations):
            raise UpstreamSchemaError(f"Incomplete rotations for {team.name}")
    return result


def parse_synergies(nodes: list[Tag], context: BuildContext) -> list[CharacterSynergy]:
    """Keep each explicitly recommended partner and their complete source explanation."""
    result = []
    for section in nodes:
        for column in section.select(".synergy-info > .column"):
            character = context.actor(require(column, ".character"))
            if character is None:
                raise UpstreamSchemaError("A synergy partner has no identity")
            result.append(
                CharacterSynergy(
                    character=character,
                    explanation=guide_blocks(require(column, ".synergy").children, context.document),
                )
            )
    if context.properties and len(result) != len(context.properties.get("synergies") or []):
        raise UpstreamSchemaError("Synergy DOM/metadata counts disagree")
    return result
