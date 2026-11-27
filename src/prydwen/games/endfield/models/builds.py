"""Character build, review, chart, and rotation contracts for card renderers."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field, HttpUrl, computed_field

from prydwen.core.models import AssetLink, Dataset, EntityAssets, Model

from .common import CharacterRef
from .stats import StatValue


class GuideLink(Model):
    """An observed inline link retained alongside plain display text."""

    text: str
    url: HttpUrl


class GuideBlock(Model):
    """Ordered safe content with media and references to separately parsed rotations."""

    kind: Literal["heading", "paragraph", "list", "table", "callout", "image", "video", "rotation"]
    text: str | None = None
    highlights: list[str] = Field(default_factory=list)
    level: int | None = Field(default=None, ge=1, le=6)
    ordered: bool = False
    items: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    links: list[GuideLink] = Field(default_factory=list)
    children: list[GuideBlock] = Field(default_factory=list)
    image: AssetLink | None = None
    media_url: HttpUrl | None = None
    video_id: str | None = None
    rotation_index: int | None = Field(default=None, ge=0)


class SectionAvailability(Model):
    """Distinguish published content from explicit placeholders or unavailable data."""

    status: Literal["available", "pending", "unavailable"]
    message: str | None = None


class BuildRating(Model):
    """A review-tab tier for one role/form and game mode, without numeric remapping."""

    role: str
    tier: str
    mode: str | None = None
    notes: list[str] = Field(default_factory=list)


class CharacterReview(Model):
    """Review ratings, strengths, weaknesses, and structured full or concise prose."""

    ratings: list[BuildRating] = Field(default_factory=list)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    content: list[GuideBlock] = Field(default_factory=list)


class EquipmentRef(Model):
    """Published equipment identity; missing joins remain unknown rather than fabricated."""

    kind: Literal["weapon", "gear", "gear_set"]
    identifier: str | None = None
    source_id: int | None = None
    name: str
    rarity: int | None = None
    slot: str | None = None
    set_name: str | None = None
    weapon_type: str | None = None
    base_attack: int | None = None
    defense: int | None = None
    stats: list[StatValue] = Field(default_factory=list)
    passive: str | None = None
    assets: EntityAssets = Field(default_factory=EntityAssets)


class BuildPerformance(Model):
    """Published comparative percentages; 100 is the baseline, not a damage share."""

    solo_percent: Decimal | None = Field(default=None, ge=0)
    team_percent: Decimal | None = Field(default=None, ge=0)


class WeaponRecommendation(Model):
    """One ranked weapon option at its source-defined potential and archetype."""

    rank: int = Field(ge=1)
    weapon: EquipmentRef
    potential: int | None = Field(default=None, ge=0)
    archetype: str | None = None
    performance: BuildPerformance = Field(default_factory=BuildPerformance)
    explanation: list[GuideBlock] = Field(default_factory=list)


class GearAlternative(Model):
    """A replacement group whose pieces may be intended to be equipped together."""

    pieces: list[EquipmentRef] = Field(default_factory=list)
    explanation: list[GuideBlock] = Field(default_factory=list)


class GearRecommendation(Model):
    """A ranked set/loadout, including duplicate kit slots and grouped replacements."""

    rank: int = Field(ge=1)
    name: str
    gear_set: EquipmentRef | None = None
    performance: BuildPerformance = Field(default_factory=BuildPerformance)
    pieces: list[EquipmentRef] = Field(default_factory=list)
    alternatives: list[GearAlternative] = Field(default_factory=list)
    explanation: list[GuideBlock] = Field(default_factory=list)


class GearPieceComparison(Model):
    """An individual-slot comparison, including the unequipped baseline."""

    slot: str
    piece: EquipmentRef | None = None
    label: str
    performance: BuildPerformance = Field(default_factory=BuildPerformance)
    has_disclaimer: bool = False


class PotentialRecommendation(Model):
    """One potential upgrade and its cumulative published solo/team comparison."""

    potential: int = Field(ge=1)
    name: str
    performance: BuildPerformance = Field(default_factory=BuildPerformance)
    explanation: list[GuideBlock] = Field(default_factory=list)


class SkillPriority(Model):
    """An archetype's ordered skill names and exact comparison operators."""

    archetype: str
    expression: str
    skills: list[str]
    operators: list[Literal[">", ">=", "="]]
    explanation: list[GuideBlock] = Field(default_factory=list)


class CharacterSynergy(Model):
    """An explicitly recommended partner and the source's explanation."""

    character: CharacterRef
    explanation: list[GuideBlock] = Field(default_factory=list)


class RotationStep(Model):
    """One ordered instruction; an unspecified actor remains None."""

    order: int = Field(ge=1)
    character: CharacterRef | None = None
    action: str


class TimelineAction(Model):
    """An action's displayed timeline position and block span, measured in seconds.

    The span describes the source visualization, not an independently verified cast time.
    """

    action: str
    start_seconds: Decimal = Field(ge=0)
    duration_seconds: Decimal = Field(gt=0)
    color: str | None = None

    @computed_field
    @property
    def end_seconds(self) -> Decimal:
        """Return the end of the displayed action block."""
        return self.start_seconds + self.duration_seconds


class TimelineRow(Model):
    """An actor's ordered lane in a source rotation timeline."""

    label: str
    character: CharacterRef | None = None
    actions: list[TimelineAction]


class TeamRotation(Model):
    """A timed lane diagram or an ordered sequence; untimed instructions stay untimed."""

    kind: Literal["timeline", "sequence"]
    title: str | None = None
    rows: list[TimelineRow] = Field(default_factory=list)
    steps: list[RotationStep] = Field(default_factory=list)
    displayed_duration_seconds: Decimal | None = Field(default=None, ge=0)


class BuildTeam(Model):
    """A source-named team with separate displayed partners and its complete roster."""

    name: str
    members: list[CharacterRef]
    displayed_members: list[CharacterRef]
    owner_implicit: bool = False
    guide: list[GuideBlock] = Field(default_factory=list)
    rotations: list[TeamRotation] = Field(default_factory=list)


class DamageContribution(Model):
    """One named pie slice, retaining zero contributions and published rounding."""

    label: str
    percent: Decimal = Field(ge=0, le=100)
    character: CharacterRef | None = None


class DamageDistribution(Model):
    """Renderer-ready pie data; chart colors are not invented from screenshots."""

    kind: Literal["pie"] = "pie"
    title: str
    scope: Literal["character", "team"]
    contributions: list[DamageContribution]
    notes: list[GuideBlock] = Field(default_factory=list)

    @computed_field
    @property
    def total_percent(self) -> Decimal:
        """Sum the published slices without renormalizing them."""
        return sum((entry.percent for entry in self.contributions), Decimal(0))


class CalculationMember(Model):
    """An operator and their actual equipment in the calculation reference setup."""

    character: CharacterRef
    weapon: EquipmentRef | None = None
    gear_set: EquipmentRef | None = None
    pieces: list[EquipmentRef] = Field(default_factory=list)


class BuildCalculations(Model):
    """The source's comparison setup, notes, and optional damage distributions."""

    members: list[CalculationMember] = Field(default_factory=list)
    charts: list[DamageDistribution] = Field(default_factory=list)
    notes: list[GuideBlock] = Field(default_factory=list)


class BuildUpdates(Model):
    """Patch labels distinguish review, build, and synergy revisions."""

    review_patch: str | None = None
    build_patch: str | None = None
    teams_patch: str | None = None


class CharacterBuild(Dataset):
    """One guide; concise output shortens prose while retaining every structured record."""

    character: CharacterRef
    detailed: bool = True
    availability: dict[str, SectionAvailability]
    updates: BuildUpdates = Field(default_factory=BuildUpdates)
    review: CharacterReview = Field(default_factory=CharacterReview)
    weapons: list[WeaponRecommendation] = Field(default_factory=list)
    gear_sets: list[GearRecommendation] = Field(default_factory=list)
    gear_pieces: list[GearPieceComparison] = Field(default_factory=list)
    potentials: list[PotentialRecommendation] = Field(default_factory=list)
    skill_priority: list[SkillPriority] = Field(default_factory=list)
    synergies: list[CharacterSynergy] = Field(default_factory=list)
    teams: list[BuildTeam] = Field(default_factory=list)
    calculations: BuildCalculations = Field(default_factory=BuildCalculations)
    notes: dict[str, list[GuideBlock]] = Field(default_factory=dict)
