"""Validated JSON caches, atomic replacement, and derived discovery metadata."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import tempfile
import weakref
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from pydantic import ValidationError

from prydwen.core.models import Dataset
from prydwen.exceptions import CacheError, CacheWriteError

logger = logging.getLogger(__name__)
Output = TypeVar("Output", bound=Dataset)
CACHE_VERSION = 1
_MANAGERS: weakref.WeakSet[JsonCache] = weakref.WeakSet()
_MUTATIONS: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[tuple[str, str], asyncio.Lock]] = (
    weakref.WeakKeyDictionary()
)


def mutation_lock(root: Path, game: str) -> asyncio.Lock:
    """Serialize cache mutations across clients sharing one loop and root."""
    locks = _MUTATIONS.setdefault(asyncio.get_running_loop(), {})
    return locks.setdefault((os.path.normcase(str(root)), game), asyncio.Lock())


def default_root(cache_dir: str | Path | None = None) -> Path:
    """Capture an absolute CWD cache root without creating it."""
    return Path(cache_dir).expanduser().absolute() if cache_dir is not None else Path.cwd() / ".prywen_cache"


def checksum(value: Any) -> str:
    """Hash a canonical JSON payload to detect accidental corruption."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def safe_path(root: Path, path: Path) -> Path:
    """Reject cache paths that escape the configured root through links or traversal."""
    if not path.absolute().is_relative_to(root.absolute()):
        raise CacheError("Cache target is outside the configured root")
    for candidate in (root, *path.relative_to(root).parents, path):
        inspected = candidate if candidate.is_absolute() else root / candidate
        if inspected.is_symlink() or getattr(inspected, "is_junction", lambda: False)():
            raise CacheError(f"Refused linked cache path: {inspected}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise CacheError("Resolved cache target is outside the configured root")
    return path


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    """Replace a complete UTF-8 document from a temporary file in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = handle.name
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


async def complete_io(operation: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Keep a mutation locked until its worker finishes, including after cancellation."""
    worker = asyncio.create_task(asyncio.to_thread(operation, *args, **kwargs))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        await asyncio.gather(worker, return_exceptions=True)
        raise


class JsonCache:
    """One game's cache manager, without shared mutable output models."""

    def __init__(self, root: Path, game: str, resources: set[str]) -> None:
        self.root = root
        self.game = game
        self.resources = resources
        self.generations = {resource: 0 for resource in resources}
        self.locks = {resource: asyncio.Lock() for resource in resources}
        _MANAGERS.add(self)

    def path(self, resource: str) -> Path:
        """Resolve a known resource key to its contained cache file."""
        if resource not in self.resources and resource != "metadata":
            raise ValueError(f"Unknown cache resource: {resource}")
        return safe_path(self.root, self.root / self.game / f"{resource}.json")

    async def read(self, resource: str, model: type[Output], source_url: str) -> Output | None:
        """Return a validated entry or a cache miss for corrupt or incompatible data."""
        path = self.path(resource)
        try:
            raw = await asyncio.to_thread(path.read_text, encoding="utf-8")
            envelope = json.loads(raw)
            if (
                envelope["cache_schema_version"] != CACHE_VERSION
                or envelope["parser_version"] != 1
                or envelope["game"] != self.game
                or envelope["resource"] != resource
                or envelope["source_url"] != source_url
                or envelope["payload_sha256"] != checksum(envelope["data"])
            ):
                return None
            data = model.model_validate(envelope["data"])
            if str(data.source.url).rstrip("/") != source_url.rstrip("/") or data.source.parser_version != 1:
                return None
            return data
        except FileNotFoundError:
            return None
        except (ValueError, KeyError, TypeError, ValidationError):
            logger.debug("Ignoring invalid %s cache", resource)
            return None
        except OSError as error:
            raise CacheError(f"Cannot read {path}: {error}") from error

    async def write(self, resource: str, data: Dataset, generation: int | None = None) -> bool:
        """Persist a validated resource; failed writes preserve the old entry."""
        payload = data.model_dump(mode="json", round_trip=True)
        envelope = {
            "cache_schema_version": CACHE_VERSION,
            "parser_version": 1,
            "game": self.game,
            "resource": resource,
            "source_url": str(data.source.url).rstrip("/"),
            "payload_sha256": checksum(payload),
            "data": payload,
        }
        async with mutation_lock(self.root, self.game):
            if generation is not None and generation != self.generations[resource]:
                return False
            try:
                await complete_io(atomic_json, self.path(resource), envelope)
                return True
            except OSError as error:
                raise CacheWriteError(f"Cannot write {resource} cache: {error}") from error

    async def update_metadata(self, resource: str, data: Dataset, generation: int | None = None) -> bool:
        """Repair a discovery fragment from the current resource without network I/O."""
        async with mutation_lock(self.root, self.game):
            if generation is not None and generation != self.generations[resource]:
                return True
            path = self.path("metadata")
            try:
                try:
                    metadata = json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))
                    if not isinstance(metadata, dict) or metadata.get("game") != self.game:
                        metadata = {}
                except (FileNotFoundError, ValueError):
                    metadata = {}
                fragments = metadata.get("resources", {})
                if not isinstance(fragments, dict):
                    fragments = {}
                fingerprint = checksum(data.model_dump(mode="json", round_trip=True))
                if (
                    isinstance(fragments.get(resource), dict)
                    and fragments[resource].get("fingerprint") == fingerprint
                ):
                    return True
                paths = [str(character.page_url) for character in getattr(data, "characters", [])]
                identifiers = [
                    {"identifier": entity.identifier, "name": entity.name}
                    for field in ("characters", "weapons", "gears", "gear_sets")
                    for entity in getattr(data, field, [])
                ]
                fragments[resource] = {
                    "fingerprint": fingerprint,
                    "source": data.source.model_dump(mode="json"),
                    "paths": paths,
                    "identifiers": identifiers,
                }
                await complete_io(
                    atomic_json,
                    path,
                    {
                        "cache_schema_version": CACHE_VERSION,
                        "game": self.game,
                        "resources": fragments,
                    },
                )
                return True
            except OSError:
                logger.warning("Could not update %s discovery metadata", self.game, exc_info=True)
                return False


async def clear_game_cache(root: Path, game: str, resources: set[str], resource: str | None = None) -> None:
    """Clear known files and invalidate active writers in this process."""
    if resource is not None and resource not in resources:
        raise ValueError(f"Unknown cache resource: {resource}")
    async with mutation_lock(root, game):
        for manager in list(_MANAGERS):
            if manager.root == root and manager.game == game:
                for key in [resource] if resource else resources:
                    manager.generations[key] += 1
        target = safe_path(root, root / game / f"{resource}.json" if resource else root / game)
        metadata_path = safe_path(root, root / game / "metadata.json")
        try:
            if resource:
                await complete_io(target.unlink, missing_ok=True)
                await complete_io(metadata_path.unlink, missing_ok=True)
            elif target.exists():
                await complete_io(shutil.rmtree, target)
        except OSError as error:
            raise CacheError(f"Cannot clear {target}: {error}") from error
