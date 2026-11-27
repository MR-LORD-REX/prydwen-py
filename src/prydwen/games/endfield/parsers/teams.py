"""Parse compositions without flattening teammate alternatives."""

import re

from prydwen.parsing.assets import asset
from prydwen.parsing.document import Document, attr, classes, require, text
from prydwen.parsing.text import slug

from ..models.teams import TeamComposition, TeamSlot, TeamTier, TeamTierList
from .common import character_ref, check_count, ensure_unique


def parse_teams(document: Document) -> TeamTierList:
    """Extract tiered team cores, ordered candidate groups, and CSS background assets."""
    root = document.root(".custom-tier-list-ake.teams")
    rows = root.select(".custom-tier")
    check_count(rows, None, "team tier rows")
    tiers = []
    for row in rows:
        raw_tier = text(require(row, ".tier-rating"))
        teams = []
        for node in row.select(".single-team"):
            name = text(require(node, "p"))
            setup = require(node, ".team-setup")
            groups = setup.select(":scope > .single")
            check_count(groups, None, "team slot groups")
            candidates = [
                [character_ref(anchor, document) for anchor in group.select("a[href]")] for group in groups
            ]
            if any(not group for group in candidates):
                from prydwen.exceptions import UpstreamSchemaError

                raise UpstreamSchemaError(f"Empty candidate group in {name}")
            background = re.search(r"url\(\s*['\"]?([^'\")]+)", attr(setup, "style") or "")
            teams.append(
                TeamComposition(
                    identifier=slug(name),
                    name=name,
                    archetype=next((label for label in classes(node) if label != "single-team"), None),
                    background=asset(background[1], document.url, name) if background else None,
                    core=candidates[0],
                    slots=[
                        TeamSlot(position=index, candidates=group)
                        for index, group in enumerate(candidates[1:], 1)
                    ],
                )
            )
        tiers.append(TeamTier(tier="".join(raw_tier.split()), raw_tier=raw_tier, teams=teams))
    ensure_unique([team.identifier for tier in tiers for team in tier.teams], "teams")
    context = document.root(".generic-page.ake-tier").get_text(" ", strip=True).split("T 0", 1)[0]
    return TeamTierList(
        source=document.source(), diagnostics=document.diagnostics, tiers=tiers, context=context
    )
