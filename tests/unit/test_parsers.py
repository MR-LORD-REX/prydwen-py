import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from prydwen.exceptions import UpstreamSchemaError
from prydwen.games.endfield.models import StatUnit
from prydwen.games.endfield.parsers.banners import parse_banners
from prydwen.games.endfield.parsers.characters import parse_characters
from prydwen.games.endfield.parsers.codes import parse_codes
from prydwen.games.endfield.parsers.common import stat
from prydwen.games.endfield.parsers.gear import parse_gear
from prydwen.games.endfield.parsers.teams import parse_teams
from prydwen.games.endfield.parsers.tiers import parse_tiers
from prydwen.games.endfield.parsers.weapons import parse_weapons
from prydwen.parsing.assets import image
from prydwen.parsing.document import Document
from prydwen.parsing.embedded import collection, inline_records
from prydwen.parsing.text import plain_html
from tests.helpers import CAPTURE_TIME

PARSERS = {
    "characters": parse_characters,
    "weapons": parse_weapons,
    "gear": parse_gear,
    "banners": parse_banners,
    "codes": parse_codes,
    "tier-list": parse_tiers,
    "team-tier-list": parse_teams,
}


def document(pages, section):
    return Document(pages[section], f"https://www.prydwen.gg/arknights-endfield/{section}", CAPTURE_TIME)


@pytest.mark.parametrize("section", PARSERS)
def test_captured_resource_roundtrip(section, pages):
    output = PARSERS[section](document(pages, section))
    payload = output.model_dump(mode="json", round_trip=True)
    assert type(output).model_validate(payload) == output
    assert output.source.fetched_at == CAPTURE_TIME
    assert output.source.content_sha256 == hashlib.sha256(pages[section].encode()).hexdigest()


def test_fixture_provenance():
    root = Path(__file__).parents[1] / "fixtures" / "endfield"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 7
    for entry in manifest:
        assert hashlib.sha256((root / entry["fixture"]).read_bytes()).hexdigest() == entry["fixture_sha256"]


def test_characters_metadata_assets_and_discovery(pages):
    output = parse_characters(document(pages, "characters"))
    assert output.total_count == 36
    akekuri = next(character for character in output.characters if character.identifier == "akekuri")
    assert (akekuri.name, akekuri.rarity, akekuri.element) == ("Akekuri", 4, "Heat")
    assert akekuri.operator_class == "Vanguard"
    assert akekuri.weapon_type == "Sword"
    assert str(akekuri.assets.icon.url).endswith("akekuri_icon.webp")
    assert str(akekuri.assets.card.url).endswith("akekuri_card.webp")
    assert any(str(asset.url).endswith("element_heat.webp") for asset in akekuri.assets.additional)
    assert akekuri.source_id and akekuri.source_unit_id == "19"
    assert output.source.updated_on.isoformat() == "2026-11-25"
    assert any(character.identifier == "mimino" and character.is_upcoming for character in output.characters)


def test_weapon_context_and_percent_units(pages):
    output = parse_weapons(document(pages, "weapons"))
    assert output.total_count == 87
    weapon = next(weapon for weapon in output.weapons if weapon.identifier == "weapon-32")
    assert weapon.source_id == 32 and weapon.base_attack == 341
    assert weapon.stat_boosts[1].stat.value == Decimal("0.2600")
    assert weapon.stat_boosts[1].stat.display == "26.00%"
    assert weapon.stat_boosts[0].rank.current == 9
    assert weapon.passive_rank.current == 9
    assert all(weapon.passive_rank.current == 4 for weapon in output.weapons if weapon.rarity == 6)
    assert "<b>" not in weapon.passive and "+33.6%" in weapon.passive


def test_gear_duplicate_names_conditional_stats_and_sets(pages):
    output = parse_gear(document(pages, "gear"))
    assert len(output.gears) == 202 and len(output.gear_sets) == 17
    duplicate = [piece for piece in output.gears if piece.name == "AIC Fieldwork Flashlight"]
    assert {piece.identifier for piece in duplicate} == {"gear-136", "gear-174"}
    assert sum(piece.set_identifier is None for piece in output.gears) == 23
    ember = next(piece for piece in output.gears if piece.identifier == "gear-175")
    assert ember.stats[0].target == "main_attribute" and ember.stats[0].stat_id is None
    assert ember.level == 70 and ember.defense == 18
    fieldwork = next(gear_set for gear_set in output.gear_sets if gear_set.identifier == "fieldwork")
    assert fieldwork.total_count == 17
    assert fieldwork.bonuses[0].required_pieces == 3
    assert not fieldwork.bonuses[0].passive.startswith("+")


def test_banners_keep_regions_teasers_and_invalid_dates(pages):
    output = parse_banners(document(pages, "banners"))
    assert output.total_count == 17
    assert len({banner.identifier for banner in output.banners}) == 17
    assert sum(banner.section == "teased" for banner in output.banners) == 9
    kay = next(banner for banner in output.banners if banner.name == "Kay")
    assert kay.schedules[0].ends_at != kay.schedules[1].ends_at
    rossi = next(banner for banner in output.banners if banner.name == "Rossi")
    assert rossi.schedules[0].ends_at.year == 2026
    assert rossi.schedules[0].starts_at.month == 12
    assert not rossi.schedules[0].is_valid
    assert rossi.schedules[0].status(CAPTURE_TIME) == "unknown"
    assert any(diagnostic.code == "invalid_banner_schedule" for diagnostic in output.diagnostics)
    with pytest.raises(ValueError, match="timezone-aware"):
        kay.schedules[0].status(datetime(2026, 11, 27))


def test_tiers_preserve_form_duplicates_and_empty_tiers(pages):
    output = parse_tiers(document(pages, "tier-list"))
    assert output.total_count == 38 and len(output.tiers) == 6
    arcane = [
        (role.role, placement.form)
        for tier in output.tiers
        for role in tier.roles
        for placement in role.placements
        if placement.character.identifier == "arcane"
    ]
    assert arcane == [("Damage", "INT Form"), ("Enabler", "WILL Form")]
    assert output.tiers[-1].tier == "T3"
    assert all(not role.placements for role in output.tiers[-1].roles)
    rossi = next(
        placement
        for tier in output.tiers
        for role in tier.roles
        for placement in role.placements
        if placement.character.identifier == "rossi"
    )
    assert rossi.watchlist and "Watchlist DOWN" in rossi.tags


def test_team_boundaries_are_preserved_without_fabricated_roles(pages):
    output = parse_teams(document(pages, "team-tier-list"))
    assert output.total_count == 15
    assert [len(tier.teams) for tier in output.tiers] == [8, 4, 3]
    arcane = output.tiers[0].teams[0]
    assert [character.identifier for character in arcane.core] == ["arcane"]
    assert [[candidate.identifier for candidate in slot.candidates] for slot in arcane.slots] == [
        ["tangtang", "perlica"],
        ["xaihi"],
        ["akekuri", "gilberta", "perlica", "liino"],
    ]
    assert all(slot.role_label is None for slot in arcane.slots)
    assert str(arcane.background.url).endswith("team_arcane.webp")


def test_codes_active_and_expired_values(pages):
    output = parse_codes(document(pages, "codes"))
    assert output.total_count == 9
    active = [code for code in output.codes if code.is_active(CAPTURE_TIME)]
    assert len(active) == 4
    reward_code = next(code for code in active if code.code == "ZAU2SYXHWX5L4ZH")
    assert [(reward.name, reward.quantity) for reward in reward_code.rewards] == [
        ("T-Credits", 5000),
        ("Arms INSP Kit", 10),
    ]
    assert reward_code.expires_at is None
    assert len([code for code in output.codes if code.is_active(datetime(2028, 1, 1, tzinfo=UTC))]) == 3


@pytest.mark.parametrize("section", ["characters", "weapons", "gear", "codes"])
def test_dom_fallback_is_explicit(section, pages):
    soup = BeautifulSoup(pages[section], "lxml")
    for script in soup.select("script"):
        script.decompose()
    fallback = dict(pages, **{section: str(soup)})
    output = PARSERS[section](document(fallback, section))
    assert output.source.extraction == "dom"
    assert any(diagnostic.code == "embedded_unavailable" for diagnostic in output.diagnostics)
    if section == "characters":
        assert output.characters[0].operator_class is None
    elif section == "codes":
        assert output.total_count == 4
        assert output.codes[0].rewards[0].name == "T-Credits"


@pytest.mark.parametrize("section", PARSERS)
def test_wrong_page_is_not_an_empty_success(section):
    with pytest.raises(UpstreamSchemaError):
        PARSERS[section](
            Document("<html><h1>Just a moment...</h1></html>", "https://www.prydwen.gg/", CAPTURE_TIME)
        )


def test_hidden_streaming_content_is_parsed(pages):
    pages = dict(pages, characters='<div hidden id="S:1">' + pages["characters"] + "</div>")
    assert parse_characters(document(pages, "characters")).total_count == 36


def test_inline_frames_join_safely_and_skip_executable_text():
    payload = "a:" + json.dumps({"characters": [{"slug": "one", "name": 'Quoted "name"'}]}) + "\n"
    scripts = "".join(
        "<script>self.__next_f.push(" + json.dumps([1, chunk]) + ")</script>"
        for chunk in [payload[:20], payload[20:]]
    )
    scripts += "<script>self.__next_f.push(execute_this())</script>"
    result = collection(inline_records(BeautifulSoup(scripts, "lxml")), "characters", {"slug", "name"})
    assert result == [{"slug": "one", "name": 'Quoted "name"'}]


@pytest.mark.parametrize(
    "raw,expected,unit",
    [
        ("+93", Decimal(93), StatUnit.FLAT),
        ("26.00%", Decimal("0.26"), StatUnit.FRACTION),
        ("1.5\u00d7", Decimal("1.5"), StatUnit.FACTOR),
        ("\u22125", Decimal(-5), StatUnit.FLAT),
        ("unknown", None, StatUnit.FLAT),
    ],
)
def test_stat_units_and_unknown_values(raw, expected, unit):
    result = stat("New Stat", raw)
    assert result.value == expected and result.unit == unit
    assert result.stat_id is None
    if unit is StatUnit.FACTOR:
        assert result.display == "1.5\u00d7"


@pytest.mark.parametrize(
    "markup,expected",
    [
        ('<img data-src="/icon.webp" src="data:image/gif;base64,abc">', "https://www.prydwen.gg/icon.webp"),
        ('<img srcset="/small.webp 1x, /large.webp 2x">', "https://www.prydwen.gg/large.webp"),
        (
            '<img src="/_next/image?url=https%3A%2F%2Fcdn.prydwen.gg%2Foriginal.webp&w=64">',
            "https://cdn.prydwen.gg/original.webp",
        ),
        ('<img src="javascript:alert(1)">', None),
    ],
)
def test_asset_sources(markup, expected):
    result = image(BeautifulSoup(markup, "lxml").img, "https://www.prydwen.gg/")
    assert (str(result.url) if result else None) == expected


def test_safe_plain_descriptions():
    assert plain_html("<p>A <b>boost</b></p><script>alert(1)</script><p>Second</p>") == "A boost\nSecond"
