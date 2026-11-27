"""Parse visible active and expired codes, preserving reward identities."""

from datetime import date

from prydwen.exceptions import UpstreamSchemaError
from prydwen.parsing.assets import asset, image
from prydwen.parsing.document import Document, attr, require, text
from prydwen.parsing.text import aware_time, integer

from ..models.codes import RedeemCode, RedeemCodes, RewardItem
from .common import ensure_unique


def parse_codes(document: Document) -> RedeemCodes:
    """Extract published code records; activity is evaluated later at read time."""
    root = document.root(".codes-page")
    records = document.catalog("codes", {"code", "rewards", "isHidden", "isManuallyExpired"})
    active_nodes = {attr(node, "data-code"): node for node in root.select("#active-code-list .code-card")}
    codes = []
    if records is not None:
        for record in records:
            if record["isHidden"]:
                continue
            active_node = active_nodes.get(record["code"])
            added = record.get("addedAt")
            expiry = aware_time(record.get("validUntil"))
            if record.get("validUntil") and expiry is None:
                raise UpstreamSchemaError(f"Invalid expiry for {record['code']}")
            codes.append(
                RedeemCode(
                    code=record["code"],
                    source_id=record.get("id"),
                    added_on=date.fromisoformat(added) if added else None,
                    expires_at=expiry,
                    expiry_timezone=record.get("expiryTimezone"),
                    manually_expired=record["isManuallyExpired"],
                    source_state="active" if active_node is not None else "expired",
                    group=attr(active_node, "data-code-group") or record.get("programId"),
                    rewards=[
                        RewardItem(
                            name=reward["name"],
                            quantity=reward.get("quantity"),
                            source_id=reward.get("rewardId"),
                            icon=asset(reward.get("imageUrl"), document.url, reward["name"]),
                        )
                        for reward in record["rewards"]
                    ],
                    legacy_rewards_text=record.get("legacyRewardsText"),
                )
            )
        published = {code.code for code in codes}
        if not set(active_nodes) <= published:
            raise UpstreamSchemaError("Active code cards are missing from the inline catalog")
    else:
        for node in active_nodes.values():
            rewards = []
            for reward in node.select(".code-reward"):
                quantity_node = reward.select_one("strong")
                label = text(reward)
                quantity_text = text(quantity_node)
                name = label.removesuffix(quantity_text).strip() if quantity_text else label
                rewards.append(
                    RewardItem(
                        name=name,
                        quantity=integer(quantity_text) if quantity_text else None,
                        icon=image(reward.select_one("img"), document.url),
                    )
                )
            expiry_raw = attr(node, "data-expires-at")
            expiry = aware_time(expiry_raw)
            if expiry_raw and expiry is None:
                raise UpstreamSchemaError("Invalid code expiry in DOM")
            codes.append(
                RedeemCode(
                    code=attr(node, "data-code") or text(require(node, "code")),
                    source_state=attr(node, "data-state") or "active",
                    manually_expired=attr(node, "data-manually-expired") == "true",
                    expires_at=expiry,
                    group=attr(node, "data-code-group"),
                    rewards=rewards,
                )
            )
        if not codes and root.select_one("#active-code-list") is None:
            raise UpstreamSchemaError("Missing active-code section")
    ensure_unique([code.code for code in codes], "codes")
    return RedeemCodes(source=document.source(), diagnostics=document.diagnostics, codes=codes)
