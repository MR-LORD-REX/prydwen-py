import gzip
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from prydwen.core.models import Model
from prydwen.exceptions import UpstreamSchemaError
from prydwen.games.endfield.build_text import concise_build, concise_text
from prydwen.games.endfield.models import CharacterBuild, CharacterReview, GuideBlock
from prydwen.games.endfield.parsers.builds import parse_character_build
from prydwen.parsing.document import Document
from tests.helpers import CAPTURE_TIME

FIXTURES = Path(__file__).parents[1] / "fixtures" / "endfield" / "character_builds"
IDENTIFIERS = [entry["identifier"] for entry in json.loads((FIXTURES / "manifest.json").read_text())]


def parse(html, identifier="si"):
    return parse_character_build(
        Document(
            html,
            f"https://www.prydwen.gg/arknights-endfield/characters/{identifier}",
            CAPTURE_TIME,
        )
    )


@pytest.mark.parametrize("identifier", IDENTIFIERS)
def test_all_character_build_fixtures(identifier, build_manifest, build_outputs):
    entry = next(entry for entry in build_manifest if entry["identifier"] == identifier)
    compressed = (FIXTURES / entry["fixture"]).read_bytes()
    assert hashlib.sha256(compressed).hexdigest() == entry["compressed_sha256"]
    assert hashlib.sha256(gzip.decompress(compressed)).hexdigest() == entry["fixture_sha256"]
    output = build_outputs[identifier]
    assert output.character.identifier == identifier
    assert output.source.extraction == "dom+embedded"
    assert not output.diagnostics
    assert len(output.weapons) == entry["counts"]["weaponRecs"]
    assert len(output.gear_sets) == entry["counts"]["gearSetRecs"]
    assert len(output.synergies) == entry["counts"]["synergies"]
    assert len(output.teams) == entry["counts"]["teamRotations"]
    assert len(output.skill_priority) == entry["counts"]["skillOrders"]
    assert len(output.calculations.charts) == entry["charts"]
    rotations = [rotation for team in output.teams for rotation in team.rotations]
    assert sum(rotation.kind == "timeline" for rotation in rotations) == entry["timelines"]
    assert sum(rotation.kind == "sequence" for rotation in rotations) == entry["sequences"]
    assert CharacterBuild.model_validate(output.model_dump(mode="json", round_trip=True)) == output


def compare_structured(full, compact):
    if isinstance(full, Model):
        assert type(full) is type(compact)
        for name in type(full).model_fields:
            if isinstance(full, CharacterBuild) and name == "detailed":
                continue
            if isinstance(full, GuideBlock) and (
                name == "text" and full.kind in {"paragraph", "callout"} or name == "items"
            ):
                original, shortened = getattr(full, name), getattr(compact, name)
                assert (original is None) == (shortened is None)
                if isinstance(original, list):
                    assert len(original) == len(shortened)
                continue
            if isinstance(full, CharacterReview) and name in {"pros", "cons"}:
                assert len(getattr(full, name)) == len(getattr(compact, name))
                continue
            compare_structured(getattr(full, name), getattr(compact, name))
    elif isinstance(full, list):
        assert len(full) == len(compact)
        for first, second in zip(full, compact, strict=True):
            compare_structured(first, second)
    elif isinstance(full, dict):
        assert full.keys() == compact.keys()
        for name in full:
            compare_structured(full[name], compact[name])
    else:
        assert full == compact


@pytest.mark.parametrize("identifier", IDENTIFIERS)
def test_concise_preserves_every_structured_field(identifier, build_outputs):
    full = build_outputs[identifier]
    original = full.model_dump_json()
    compact = concise_build(full)
    assert full.detailed and not compact.detailed
    compare_structured(full, compact)
    assert full.model_dump_json() == original
    assert CharacterBuild.model_validate(compact.model_dump(mode="json", round_trip=True)) == compact


def test_si_build_percentages_pieces_and_pie(build_outputs):
    result = build_outputs["si"]
    assert [(rating.role, rating.tier) for rating in result.review.ratings] == [
        ("Buffer", "T0"),
        ("Damage", "T0"),
    ]
    assert len(result.review.pros) == len(result.review.cons) == 4
    assert result.weapons[0].weapon.name == "Jade Vessel"
    assert result.weapons[0].weapon.identifier == "weapon-80"
    assert result.weapons[0].performance.solo_percent == Decimal("100.00")
    assert [piece.slot for piece in result.gear_sets[0].pieces] == ["Armor", "Gloves", "Kit", "Kit"]
    replacement = result.gear_sets[0].alternatives[2].pieces
    assert [piece.name for piece in replacement] == ["Redeemer Armor", "Type 50 Yinglung Beacon"]
    assert all(piece.identifier for piece in replacement)
    chart = result.calculations.charts[0]
    assert chart.kind == "pie" and chart.total_percent == Decimal(100)
    assert [(slice.label, slice.percent) for slice in chart.contributions] == [
        ("Basic Attack", Decimal("20.5")),
        ("Battle Skill", Decimal("0.5")),
        ("Combo Skill", Decimal("76.4")),
        ("Other", Decimal("2.6")),
    ]
    assert result.skill_priority[0].operators == [">", "=", ">"]


def test_si_timeline_and_implicit_team_owner(build_outputs):
    team = build_outputs["si"].teams[0]
    assert team.owner_implicit and len(team.displayed_members) == 3 and len(team.members) == 4
    assert team.members[0].identifier == "si"
    timeline = team.rotations[0]
    assert timeline.kind == "timeline" and not timeline.steps
    assert [row.character.identifier for row in timeline.rows] == ["arcane", "tangtang", "xaihi", "si"]
    action = timeline.rows[0].actions[0]
    assert (action.action, action.start_seconds, action.duration_seconds, action.end_seconds) == (
        "Combo Skill",
        Decimal(1),
        Decimal("0.5"),
        Decimal("1.5"),
    )
    assert timeline.rows[3].actions[0].start_seconds == Decimal(0)
    assert [block.rotation_index for block in team.guide if block.kind == "rotation"] == [0]
    assert any(block.kind == "video" and block.video_id == "Zu0yTDSB9zU" for block in team.guide)


def test_untimed_sequences_do_not_guess_actor_or_seconds(build_outputs):
    sequence = build_outputs["arclight"].teams[0].rotations[0]
    assert sequence.kind == "sequence" and sequence.title == "Opening rotation"
    assert sequence.displayed_duration_seconds is None and not sequence.rows
    assert len(sequence.steps) == 9
    assert sequence.steps[0].character.identifier == "antal"
    assert sequence.steps[3].action == "Final Strike" and sequence.steps[3].character is None


def test_other_archetypes_setless_loadouts_and_unpublished_sections(build_outputs):
    priorities = build_outputs["endministrator"].skill_priority
    assert [priority.archetype for priority in priorities] == ["Off Field", "Main Field"]
    assert priorities[0].operators == ["=", ">=", ">="]
    assert any(option.archetype == "Specialist" for option in build_outputs["arcane"].weapons)
    setless = build_outputs["wulfgard"].gear_sets[0]
    assert setless.name == "No Set" and setless.gear_set is None and setless.pieces
    pending = build_outputs["mimino"]
    assert not pending.weapons and not pending.teams
    assert pending.availability["weapons"].status == "pending"
    assert pending.availability["calculations"].status == "unavailable"


def test_gear_comparisons_keep_baselines_and_disclaimer_markers(build_outputs):
    entries = build_outputs["arclight"].gear_pieces
    assert len(entries) == 28
    assert len([entry for entry in entries if entry.piece is None]) == 3
    assert any(entry.has_disclaimer and entry.piece is not None for entry in entries)
    assert all(entry.performance.solo_percent == Decimal(100) for entry in entries if entry.piece is None)


def test_dom_fallback_preserves_timelines_and_reports_missing_pie_data(build_pages):
    soup = BeautifulSoup(build_pages["si"], "lxml")
    for script in soup.select("script"):
        script.decompose()
    result = parse(str(soup))
    assert len(result.weapons) == 4 and len(result.teams) == 4
    assert len(result.teams[0].rotations[0].rows) == 4
    assert not result.calculations.charts
    assert {diagnostic.code for diagnostic in result.diagnostics} >= {
        "build_metadata_unavailable",
        "chart_data_unavailable",
    }


def test_corrupt_timeline_scale_and_missing_guide_section_fail(build_pages):
    soup = BeautifulSoup(build_pages["si"], "lxml")
    soup.select(".timeline-second-marker")[2]["style"] = "left:999px"
    with pytest.raises(UpstreamSchemaError, match="geometry"):
        parse(str(soup))
    soup = BeautifulSoup(build_pages["si"], "lxml")
    next(
        node for node in soup.select(".content-header") if node.get_text(strip=True) == "Best Weapons"
    ).decompose()
    with pytest.raises(UpstreamSchemaError, match="sections"):
        parse(str(soup))


def test_wrong_page_and_expected_identity_are_rejected(build_pages):
    with pytest.raises(UpstreamSchemaError):
        parse("<html><h1>Unexpected</h1></html>")
    with pytest.raises(UpstreamSchemaError, match="metadata"):
        parse(build_pages["si"], "akekuri")


def test_concise_extracts_source_sentences_and_keeps_emphasis(build_outputs):
    full = build_outputs["si"]
    compact = concise_build(full)
    assert len(compact.model_dump_json()) < len(full.model_dump_json())
    assert compact.teams[0].rotations == full.teams[0].rotations
    assert compact.calculations.charts == full.calculations.charts
    assert compact.weapons[0].explanation != full.weapons[0].explanation
    text = (
        "Use the recommended weapon for this setup. "
        + "Additional context is provided for this example. " * 9
        + "Only activate the marked effect after the target is staggered."
    )
    shorter = concise_text(text, ["Only activate"])
    assert "Use the recommended" in shorter and "Only activate" in shorter
    assert len(shorter) < len(text)
