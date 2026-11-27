"""Declared banner groups and regional schedules without silent date fixes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, HttpUrl, computed_field

from prydwen.core.models import AssetLink, Dataset, Model

BannerType = Literal["character", "weapon", "both"]
Region = Literal["asia", "eu", "na"]
TemporalStatus = Literal["current", "upcoming", "ended", "unknown"]


class BannerSchedule(Model):
    """Original regional times and their chronology validity."""

    region: Region
    raw_start: str | None
    raw_end: str | None
    starts_at: AwareDatetime | None
    ends_at: AwareDatetime | None
    end_unannounced: bool
    is_valid: bool

    def status(self, at: datetime) -> TemporalStatus:
        """Evaluate a valid schedule at an explicit timezone-aware instant."""
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("at must be timezone-aware")
        if not self.is_valid:
            return "unknown"
        if self.starts_at is not None and at < self.starts_at:
            return "upcoming"
        if self.ends_at is not None and at >= self.ends_at:
            return "ended"
        if self.starts_at is not None and self.ends_at is not None:
            return "current"
        return "unknown"


class FeaturedEntity(Model):
    """An actual featured link, including catalog search URLs."""

    name: str
    url: HttpUrl


class BannerChip(Model):
    """A labeled element, class, or weapon icon on a banner."""

    label: str
    description: str | None = None
    icon: AssetLink | None = None


class Banner(Model):
    """One source banner; local keys do not imply official game identity."""

    identifier: str
    name: str
    banner_type: str
    section: str
    patch: str | None
    banner_kind: str | None
    description: str
    art: AssetLink | None
    featured: list[FeaturedEntity]
    chips: list[BannerChip]
    schedules: list[BannerSchedule]


class AllBanners(Dataset):
    """An ordered collection of source banners."""

    banners: list[Banner]

    @computed_field
    @property
    def total_count(self) -> int:
        """Return the number of banners after the requested filter."""
        return len(self.banners)
