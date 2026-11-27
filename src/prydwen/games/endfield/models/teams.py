"""Tiered compositions with ordered alternatives for each teammate slot."""

from pydantic import computed_field

from prydwen.core.models import AssetLink, Dataset, Model

from .common import CharacterRef


class TeamSlot(Model):
    """Candidate alternatives in one slot, without an invented role label."""

    position: int
    candidates: list[CharacterRef]
    role_label: str | None = None


class TeamComposition(Model):
    """A core character and independent source-defined teammate groups."""

    identifier: str
    name: str
    archetype: str | None
    background: AssetLink | None
    core: list[CharacterRef]
    slots: list[TeamSlot]


class TeamTier(Model):
    """An editorial team tier row."""

    tier: str
    raw_tier: str
    teams: list[TeamComposition]


class TeamTierList(Dataset):
    """Ordered team tiers and their stated endgame context."""

    tiers: list[TeamTier]
    context: str

    @computed_field
    @property
    def total_count(self) -> int:
        """Return the number of compositions, not expanded combinations."""
        return sum(len(tier.teams) for tier in self.tiers)
