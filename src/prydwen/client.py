"""Game entry points and cache utilities independent of any game's data API."""

from pathlib import Path

from .core.cache import clear_game_cache, default_root
from .games.endfield.client import EndfieldClient
from .games.endfield.endpoints import GAME, RESOURCES


class Prydwen:
    """Expose game constructors and common maintenance operations."""

    Endfield = EndfieldClient

    @staticmethod
    async def clear_cache(
        game: str | None = None,
        *,
        resource: str | None = None,
        cache_dir: str | Path | None = None,
    ) -> None:
        """Clear known game/resource caches beneath the configured root.

        Args:
            game: 'arknights-endfield' or None for all supported games.
            resource: Optional resource key, such as 'characters' or 'tier_list'.
            cache_dir: Root override; defaults to CWD/.prywen_cache.
        Raises:
            ValueError: If a game or resource is not supported.
            CacheError: If a target escapes the cache root or deletion fails.
        """
        if game not in {None, GAME}:
            raise ValueError(f"Unsupported game: {game}")
        await clear_game_cache(default_root(cache_dir), GAME, set(RESOURCES), resource)
