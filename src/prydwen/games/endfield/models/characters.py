"""Character summaries available from the Endfield index."""

from pydantic import Field, computed_field

from prydwen.core.models import Dataset, Model

from .common import CharacterRef


class SourceTierRating(Model):
    """Index ratings retained without guessing their numeric tier mapping."""

    category: str
    rating: str
    tags: str = ""
    change: str = ""
    watchlist: str = ""


class Character(CharacterRef):
    """General operator data; detailed builds and skills are a future resource."""

    synergy_tags: list[str] = Field(default_factory=list)
    is_upcoming: bool | None = None
    is_new: bool | None = None
    tier_ratings: list[SourceTierRating] = Field(default_factory=list)


class AllCharacters(Dataset):
    """Every operator in the inspected character index."""

    characters: list[Character]

    @computed_field
    @property
    def total_count(self) -> int:
        """Return the number of characters, including upcoming operators."""
        return len(self.characters)
