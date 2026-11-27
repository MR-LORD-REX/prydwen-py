"""Gear pieces and set bonuses with distinct source identities."""

from pydantic import computed_field

from prydwen.core.models import Dataset, EntityAssets, Model

from .stats import StatValue


class Gear(Model):
    """One gear piece, identified independently of its display name."""

    identifier: str
    source_id: int | None = None
    name: str
    slot: str
    level: int | None = None
    defense: int
    stats: list[StatValue]
    set_identifier: str | None = None
    assets: EntityAssets


class GearSetBonus(Model):
    """A set bonus at a source-defined piece count."""

    required_pieces: int
    stats: list[StatValue]
    passive: str


class GearSet(Model):
    """Set metadata, bonuses, and all catalog pieces belonging to it."""

    identifier: str
    name: str
    source_code: str | None = None
    bonuses: list[GearSetBonus]
    gears: list[Gear]

    @computed_field
    @property
    def total_count(self) -> int:
        """Return the number of pieces in this set."""
        return len(self.gears)


class AllGear(Dataset):
    """The single-page gear and gear-set catalog."""

    gears: list[Gear]
    gear_sets: list[GearSet]
