"""Explicit displayed stat units, preserving unknown labels and values."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import computed_field

from prydwen.core.models import Model


class StatUnit(StrEnum):
    """Units follow the stat reference rather than numeric magnitude."""

    FLAT = "flat"
    FRACTION = "fraction"
    FACTOR = "factor"
    NUMBER = "number"


class StatValue(Model):
    """One displayed modifier with its original label and text."""

    key: str
    label: str
    value: Decimal | None
    unit: StatUnit
    raw_value: str
    stat_id: int | None = None
    target: str = "property"
    decimal_places: int = 0

    @computed_field
    @property
    def display(self) -> str:
        """Return deterministic percent text or the source scalar value."""
        if self.value is None:
            return self.raw_value
        if self.unit is StatUnit.FRACTION:
            quantum = Decimal(1).scaleb(-self.decimal_places)
            amount = (self.value * 100).quantize(quantum, rounding=ROUND_HALF_UP)
            return f"{amount:.{self.decimal_places}f}%"
        if self.unit is StatUnit.FACTOR:
            return f"{self.value:g}\u00d7"
        return f"{self.value:g}"


class BoostRank(Model):
    """The source's boost rank, independent of weapon level."""

    current: int
    maximum: int


class StatBoost(Model):
    """A weapon stat modifier and its displayed rank."""

    slot: int
    stat: StatValue
    rank: BoostRank | None = None
