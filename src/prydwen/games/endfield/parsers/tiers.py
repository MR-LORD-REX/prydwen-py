"""Parse editorial tiers by role, retaining duplicate character placements."""

from prydwen.parsing.document import Document, classes, require, text

from ..models.tiers import CharacterTier, TierList, TierPlacement, TierRole
from .common import character_ref, check_count


def parse_tiers(document: Document) -> TierList:
    """Extract tier rows, role buckets, form tags, and source badges."""
    root = document.root(".custom-tier-list-ake:not(.teams)")
    rows = root.select(".custom-tier")
    check_count(rows, None, "tier rows")
    role_labels = {}
    for header in root.select(".custom-header"):
        for role in ("dps", "enabler", "buffer"):
            if role in classes(header):
                role_labels[role] = text(header)
    tiers = []
    for row in rows:
        raw_tier = text(require(row, ".tier-rating"))
        roles = []
        for bucket in row.select(".custom-tier-burst"):
            role_key = next((role for role in role_labels if role in classes(bucket)), None)
            role = role_labels[role_key] if role_key else text(bucket.select_one(".burst-type-mobile"))
            if not role:
                from prydwen.exceptions import UpstreamSchemaError

                raise UpstreamSchemaError("Unknown tier role without a displayed label")
            placements = []
            for card in bucket.select(".avatar-card"):
                tags = [text(tag) for tag in card.select(".tier-list-tags .single-tag")]
                flags = {
                    label for badge in card.select(".floating-right-corner .item") for label in classes(badge)
                }
                placements.append(
                    TierPlacement(
                        character=character_ref(card, document),
                        tags=tags,
                        form=next((tag for tag in tags if "form" in tag.casefold()), None),
                        is_new="new" in flags,
                        movement="down" if "down" in flags else "up" if "up" in flags else None,
                        watchlist="watchlist" in flags or any("watchlist" in tag.casefold() for tag in tags),
                    )
                )
            roles.append(TierRole(role=role, placements=placements))
        tiers.append(CharacterTier(tier="".join(raw_tier.split()), raw_tier=raw_tier, roles=roles))
    context = document.root(".generic-page.ake-tier").get_text(" ", strip=True).split("T0", 1)[0]
    return TierList(source=document.source(), diagnostics=document.diagnostics, tiers=tiers, context=context)
