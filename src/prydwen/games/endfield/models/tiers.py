"""Editorial tier placements, preserving forms and empty role buckets."""

from pydantic import computed_field

from prydwen.core.models import Dataset, Model

from .common import CharacterRef


class TierPlacement(Model):
    """One occurrence of a character in an editorial role."""

    character: CharacterRef
    tags: list[str]
    form: str | None
    is_new: bool
    movement: str | None
    watchlist: bool


class TierRole(Model):
    """A displayed role column, including an empty one."""

    role: str
    placements: list[TierPlacement]


class CharacterTier(Model):
    """A source-ordered tier row."""

    tier: str
    raw_tier: str
    roles: list[TierRole]


class TierList(Dataset):
    """All character tiers with the source's editorial assumptions."""

    tiers: list[CharacterTier]
    context: str

    @computed_field
    @property
    def total_count(self) -> int:
        """Return placement count; one character may have several placements."""
        return sum(len(role.placements) for tier in self.tiers for role in tier.roles)
