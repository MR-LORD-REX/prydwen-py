"""Parse the operator index and its optional inline catalog metadata."""

from prydwen.core.models import EntityAssets
from prydwen.exceptions import UpstreamSchemaError
from prydwen.parsing.assets import asset
from prydwen.parsing.document import Document

from ..models.characters import AllCharacters, Character, SourceTierRating
from .common import character_ref, check_count, ensure_unique


def parse_characters(document: Document) -> AllCharacters:
    """Extract character identities, general metadata, and actual asset links."""
    root = document.root(".employees-container.ake-cards")
    nodes = root.select(".avatar-card")
    records = document.catalog("characters", {"slug", "name", "rarity"})
    check_count(nodes, records, "characters")
    indexed = {record["slug"]: record for record in records or []}
    ensure_unique([record["slug"] for record in records or []], "inline characters")
    characters = []
    for node in nodes:
        reference = character_ref(node, document)
        record = indexed.get(reference.identifier)
        values = reference.model_dump()
        if record is not None:
            if record["name"] != reference.name or int(record["rarity"]) != reference.rarity:
                raise UpstreamSchemaError(f"Conflicting character identity: {reference.identifier}")
            values.update(
                source_id=str(record["id"]) if record.get("id") is not None else None,
                source_unit_id=str(record["unitId"]) if record.get("unitId") is not None else None,
                element=record.get("element"),
                operator_class=record.get("class"),
                weapon_type=record.get("weaponType") or record.get("weapon"),
                assets=EntityAssets(
                    icon=asset(record.get("smallImage"), document.url, reference.name),
                    card=reference.assets.card
                    or asset(record.get("cardImage"), document.url, reference.name),
                    additional=reference.assets.additional,
                ),
                synergy_tags=record.get("synergyTags", []),
                is_upcoming=record.get("upcoming"),
                is_new=record.get("isNew"),
                tier_ratings=[
                    SourceTierRating(
                        category=rating["category"],
                        rating=str(rating["rating"]),
                        tags=rating.get("tags", ""),
                        change=rating.get("change", ""),
                        watchlist=rating.get("watchlist", ""),
                    )
                    for rating in record.get("tierRatings", [])
                ],
            )
        elif records is not None:
            raise UpstreamSchemaError(f"Missing inline identity: {reference.identifier}")
        characters.append(Character(**values))
    ensure_unique([character.identifier for character in characters], "characters")
    return AllCharacters(source=document.source(), diagnostics=document.diagnostics, characters=characters)
