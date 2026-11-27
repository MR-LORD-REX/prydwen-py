"""Reusable Endfield references with source identifiers."""

from pydantic import Field, HttpUrl

from prydwen.core.models import EntityAssets, Model


class CharacterRef(Model):
    """A character identity observed in a catalog, tier list, or team."""

    identifier: str
    name: str
    page_url: HttpUrl
    source_id: str | None = None
    source_unit_id: str | None = None
    rarity: int | None = None
    element: str | None = None
    operator_class: str | None = None
    weapon_type: str | None = None
    assets: EntityAssets = Field(default_factory=EntityAssets)
