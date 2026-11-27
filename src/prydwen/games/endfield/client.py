"""Public asynchronous Endfield methods, separate from HTML parsing."""

from __future__ import annotations

from pathlib import Path

from prydwen.core.client import GameClient
from prydwen.core.models import Identifier
from prydwen.core.transport import PageTransport
from prydwen.exceptions import NotFoundError

from .endpoints import GAME, RESOURCES, resource_url
from .models import (
    AllBanners,
    AllCharacters,
    AllGear,
    AllWeapons,
    BannerType,
    Gear,
    GearSet,
    RedeemCodes,
    Region,
    TeamTierList,
    TierList,
)
from .parsers.banners import parse_banners
from .parsers.characters import parse_characters
from .parsers.codes import parse_codes
from .parsers.gear import parse_gear
from .parsers.teams import parse_teams
from .parsers.tiers import parse_tiers
from .parsers.weapons import parse_weapons


class EndfieldClient(GameClient):
    """Access Endfield guides with a persistent CWD cache.

    Args:
        cache_dir: Cache root override; defaults to CWD/.prywen_cache.
        timeout: Positive timeout in seconds for network requests.
        request_interval: Minimum seconds between requests; defaults to 10.
        max_response_bytes: Maximum decoded response body size.
        transport: Optional caller-owned transport, useful for offline integrations.
    """

    def __init__(
        self,
        *,
        cache_dir: str | Path | None = None,
        timeout: float = 30,
        request_interval: float = 10,
        max_response_bytes: int = 8_000_000,
        transport: PageTransport | None = None,
    ) -> None:
        super().__init__(
            GAME,
            set(RESOURCES),
            cache_dir=cache_dir,
            timeout=timeout,
            request_interval=request_interval,
            max_response_bytes=max_response_bytes,
            transport=transport,
        )

    async def list_characters(self, *, force_new: bool = False) -> list[Identifier]:
        """List character names and identifiers for future character-specific lookups.

        Args:
            force_new: Fetch and replace the character cache instead of reusing it.
        Returns:
            Name/identifier objects in source order, including upcoming operators.
        Raises:
            PrydwenError: If retrieval, parsing, client lifecycle, or storage fails.
        """
        data = await self.characters(force_new=force_new)
        return [
            Identifier(name=character.name, identifier=character.identifier) for character in data.characters
        ]

    async def list_weapons(self, *, force_new: bool = False) -> list[Identifier]:
        """List weapon names and source identifiers without requesting detail pages.

        Args:
            force_new: Fetch and replace the weapons cache.
        Returns:
            Name/identifier objects from the complete weapon catalog.
        Raises:
            PrydwenError: If retrieval, parsing, client lifecycle, or storage fails.
        """
        data = await self._load("weapons", resource_url("weapons"), AllWeapons, parse_weapons, force_new)
        return [Identifier(name=weapon.name, identifier=weapon.identifier) for weapon in data.weapons]

    async def list_gears(self, *, force_new: bool = False) -> list[Identifier]:
        """List gear names and distinct identifiers, preserving duplicate names.

        Args:
            force_new: Fetch and replace the shared gear/set cache.
        Returns:
            Name/identifier objects accepted by gear().
        Raises:
            PrydwenError: If retrieval, parsing, client lifecycle, or storage fails.
        """
        data = await self._gears(force_new)
        return [Identifier(name=gear.name, identifier=gear.identifier) for gear in data.gears]

    async def list_gear_sets(self, *, force_new: bool = False) -> list[Identifier]:
        """List gear-set names and the identifiers accepted by gear_set().

        Args:
            force_new: Fetch and replace the shared gear/set cache.
        Returns:
            Name/identifier objects for named sets; setless pieces are excluded.
        Raises:
            PrydwenError: If retrieval, parsing, client lifecycle, or storage fails.
        """
        data = await self._gears(force_new)
        return [Identifier(name=gear_set.name, identifier=gear_set.identifier) for gear_set in data.gear_sets]

    async def characters(self, *, force_new: bool = False) -> AllCharacters:
        """Retrieve general character data from the operator index.

        Args:
            force_new: Bypass cache and fetch the character index again.
        Returns:
            AllCharacters with characters, total_count, assets, and provenance.
        Raises:
            PrydwenError: If retrieval, parsing, client lifecycle, or storage fails.
        """
        return await self._load(
            "characters", resource_url("characters"), AllCharacters, parse_characters, force_new
        )

    async def gear(self, identifier: str, *, force_new: bool = False) -> Gear:
        """Retrieve one gear piece using an identifier returned by list_gears().

        Args:
            identifier: The exact gear identifier, not a potentially duplicate name.
            force_new: Refresh the shared gear/set catalog before looking it up.
        Returns:
            Gear containing displayed stats, level, set membership, and assets.
        Raises:
            NotFoundError: If the identifier is absent from the catalog.
            PrydwenError: If retrieval, parsing, client lifecycle, or storage fails.
        """
        self._identifier(identifier)
        data = await self._gears(force_new)
        for piece in data.gears:
            if piece.identifier == identifier:
                return piece
        raise NotFoundError(f"{resource_url('gear')}#{identifier}", 404)

    async def gear_set(self, identifier: str, *, force_new: bool = False) -> GearSet:
        """Retrieve a named gear set and all of its catalog pieces.

        Args:
            identifier: The exact identifier returned by list_gear_sets().
            force_new: Refresh the shared gear/set catalog before looking it up.
        Returns:
            GearSet with gears, total_count, and source-defined set bonuses.
        Raises:
            NotFoundError: If the set identifier is absent from the catalog.
            PrydwenError: If retrieval, parsing, client lifecycle, or storage fails.
        """
        self._identifier(identifier)
        data = await self._gears(force_new)
        for gear_set in data.gear_sets:
            if gear_set.identifier == identifier:
                return gear_set
        raise NotFoundError(f"{resource_url('gear')}#{identifier}", 404)

    async def banners(self, banner_type: BannerType = "both", *, force_new: bool = False) -> AllBanners:
        """Retrieve all banners, including scheduled and teased entries.

        Args:
            banner_type: 'character', 'weapon', or 'both' (default).
            force_new: Refresh the banner page instead of reusing the cache.
        Returns:
            AllBanners preserving declared sections and all regional schedules.
        Raises:
            ValueError: If banner_type is unsupported.
            PrydwenError: If retrieval, parsing, client lifecycle, or storage fails.
        """
        if banner_type not in {"character", "weapon", "both"}:
            raise ValueError("banner_type must be 'character', 'weapon', or 'both'")
        data = await self._load("banners", resource_url("banners"), AllBanners, parse_banners, force_new)
        return data.model_copy(
            update={
                "banners": [
                    banner
                    for banner in data.banners
                    if banner_type == "both" or banner.banner_type == banner_type
                ]
            }
        )

    async def current_banners(
        self,
        banner_type: BannerType = "both",
        *,
        region: Region = "asia",
        force_new: bool = False,
    ) -> AllBanners:
        """Retrieve source-declared current banners, excluding reliably elapsed schedules.

        Args:
            banner_type: 'character', 'weapon', or 'both' (default).
            region: Regional time schedule: 'asia' (default), 'eu', or 'na'.
            force_new: Refresh the shared banner cache first.
        Returns:
            AllBanners for the current section; invalid/unknown dates stay declared
            current with diagnostics rather than being silently corrected.
        Raises:
            ValueError: If a filter is unsupported.
            PrydwenError: If retrieval, parsing, client lifecycle, or storage fails.
        """
        self._region(region)
        data = await self.banners(banner_type, force_new=force_new)
        now = self._now()
        return data.model_copy(
            update={
                "banners": [
                    banner
                    for banner in data.banners
                    if banner.section == "current"
                    and not any(
                        schedule.region == region and schedule.status(now) in {"ended", "upcoming"}
                        for schedule in banner.schedules
                    )
                ]
            }
        )

    async def upcoming_banners(
        self,
        banner_type: BannerType = "both",
        *,
        region: Region = "asia",
        force_new: bool = False,
    ) -> AllBanners:
        """Retrieve scheduled-next and teased banners from the source's upcoming groups.

        Args:
            banner_type: 'character', 'weapon', or 'both' (default).
            region: Regional time schedule: 'asia' (default), 'eu', or 'na'.
            force_new: Refresh the shared banner cache first.
        Returns:
            AllBanners from upcoming/teased sections, excluding reliably started or
            elapsed schedules. Unknown/invalid schedules retain their source group.
        Raises:
            ValueError: If a filter is unsupported.
            PrydwenError: If retrieval, parsing, client lifecycle, or storage fails.
        """
        self._region(region)
        data = await self.banners(banner_type, force_new=force_new)
        now = self._now()
        return data.model_copy(
            update={
                "banners": [
                    banner
                    for banner in data.banners
                    if banner.section in {"upcoming", "teased"}
                    and not any(
                        schedule.region == region and schedule.status(now) in {"ended", "current"}
                        for schedule in banner.schedules
                    )
                ]
            }
        )

    async def redeem_codes(self, *, force_new: bool = False) -> RedeemCodes:
        """Retrieve visible source-listed active codes and their item rewards.

        Args:
            force_new: Refresh the codes page instead of reusing the cache.
        Returns:
            RedeemCodes after manual and known timestamp expiry checks at read time.
            Missing expiry stays unknown; the library does not attempt redemption.
        Raises:
            PrydwenError: If retrieval, parsing, client lifecycle, or storage fails.
        """
        data = await self._load("codes", resource_url("codes"), RedeemCodes, parse_codes, force_new)
        now = self._now()
        return data.model_copy(update={"codes": [code for code in data.codes if code.is_active(now)]})

    async def tier_list(self, *, force_new: bool = False) -> TierList:
        """Retrieve the character tier list by tier and editorial role.

        Args:
            force_new: Refresh the character-tier page instead of reusing its cache.
        Returns:
            TierList retaining role/form duplicates, source tags, and empty tiers.
        Raises:
            PrydwenError: If retrieval, parsing, client lifecycle, or storage fails.
        """
        return await self._load("tier_list", resource_url("tier_list"), TierList, parse_tiers, force_new)

    async def team_tier_list(self, *, force_new: bool = False) -> TeamTierList:
        """Retrieve tiered teams with a core and ordered alternative teammate slots.

        Args:
            force_new: Refresh the team-tier page instead of reusing its cache.
        Returns:
            TeamTierList with grouped candidates and actual team background URLs.
        Raises:
            PrydwenError: If retrieval, parsing, client lifecycle, or storage fails.
        """
        return await self._load(
            "team_tier_list", resource_url("team_tier_list"), TeamTierList, parse_teams, force_new
        )

    async def _gears(self, force_new: bool) -> AllGear:
        """Load the one catalog shared by gear and set operations."""
        return await self._load("gear", resource_url("gear"), AllGear, parse_gear, force_new)

    @staticmethod
    def _identifier(identifier: str) -> None:
        """Validate lookup inputs before any resource request."""
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError("identifier must be a nonempty string from a list method")

    @staticmethod
    def _region(region: str) -> None:
        """Validate a regional banner filter before requesting the catalog."""
        if region not in {"asia", "eu", "na"}:
            raise ValueError("region must be 'asia', 'eu', or 'na'")
