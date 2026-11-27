"""Visible redeem codes and rewards with read-time expiry evaluation."""

from datetime import date, datetime

from pydantic import AwareDatetime, computed_field

from prydwen.core.models import AssetLink, Dataset, Model


class RewardItem(Model):
    """One code reward and its observed image."""

    name: str
    quantity: int | None
    source_id: str | None = None
    icon: AssetLink | None = None


class RedeemCode(Model):
    """A source-listed code; unknown expiry does not guarantee redeemability."""

    code: str
    source_id: str | None = None
    added_on: date | None = None
    expires_at: AwareDatetime | None = None
    expiry_timezone: str | None = None
    manually_expired: bool = False
    source_state: str
    group: str | None = None
    rewards: list[RewardItem]
    legacy_rewards_text: str | None = None

    def is_active(self, at: datetime) -> bool:
        """Apply manual expiry, known timestamps, and the source-listed state."""
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("at must be timezone-aware")
        if self.manually_expired or self.source_state == "expired":
            return False
        if self.expires_at is not None and at >= self.expires_at:
            return False
        return self.source_state == "active"


class RedeemCodes(Dataset):
    """A filtered collection of codes with its original source provenance."""

    codes: list[RedeemCode]

    @computed_field
    @property
    def total_count(self) -> int:
        """Return the number of codes in this result."""
        return len(self.codes)
