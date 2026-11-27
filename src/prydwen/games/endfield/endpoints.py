"""Static Endfield resources; entity paths are discovered from their HTML."""

from typing import Final

GAME: Final = "arknights-endfield"
BASE_URL: Final = "https://www.prydwen.gg"
RESOURCES: Final = {
    "characters": "characters",
    "weapons": "weapons",
    "gear": "gear",
    "banners": "banners",
    "tier_list": "tier-list",
    "team_tier_list": "team-tier-list",
    "codes": "codes",
}


def resource_url(resource: str) -> str:
    """Return the canonical URL for a known section resource."""
    return f"{BASE_URL}/{GAME}/{RESOURCES[resource]}"
