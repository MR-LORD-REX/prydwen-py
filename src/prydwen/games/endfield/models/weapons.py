"""Weapon catalog data and explicit boost context."""

from pydantic import computed_field

from prydwen.core.models import Dataset, EntityAssets, Model

from .stats import BoostRank, StatBoost


class Weapon(Model):
    """One catalog weapon with displayed ATK, boosts, and passive text."""

    identifier: str
    source_id: int | None = None
    name: str
    weapon_type: str
    rarity: int
    base_attack: int
    stat_boosts: list[StatBoost]
    passive: str
    passive_rank: BoostRank | None = None
    assets: EntityAssets


class AllWeapons(Dataset):
    """Internal typed weapon catalog shared by list operations."""

    weapons: list[Weapon]

    @computed_field
    @property
    def total_count(self) -> int:
        """Return the number of distinct weapons."""
        return len(self.weapons)
