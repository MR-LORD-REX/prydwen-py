import asyncio
import threading

import pytest

from prydwen.core import cache as cache_module
from prydwen.core.cache import JsonCache, clear_game_cache, safe_path
from prydwen.exceptions import CacheError, CacheWriteError
from prydwen.games.endfield.parsers.characters import parse_characters
from prydwen.parsing.document import Document
from tests.helpers import CAPTURE_TIME


def test_atomic_failure_keeps_old_file(tmp_path, monkeypatch):
    target = tmp_path / "characters.json"
    target.write_text("old", encoding="utf-8")

    def fail_replace(*args):
        raise OSError("disk failure")

    monkeypatch.setattr(cache_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk failure"):
        cache_module.atomic_json(target, {"new": True})
    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.iterdir()) == [target]


async def test_write_error_is_typed(tmp_path, pages, monkeypatch):
    cache = JsonCache(tmp_path, "arknights-endfield", {"characters"})
    data = parse_characters(
        Document(pages["characters"], "https://www.prydwen.gg/arknights-endfield/characters", CAPTURE_TIME)
    )

    def fail_write(*args):
        raise OSError("full")

    monkeypatch.setattr(cache_module, "atomic_json", fail_write)
    with pytest.raises(CacheWriteError, match="full"):
        await cache.write("characters", data)


def test_cache_path_rejects_symlinks(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "cache"
    root.mkdir()
    link = root / "arknights-endfield"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not permit creating directory symlinks")
    with pytest.raises(CacheError, match="linked"):
        safe_path(root, link / "characters.json")
    assert outside.is_dir()


def test_cache_path_rejects_parent_traversal(tmp_path):
    with pytest.raises(CacheError):
        safe_path(tmp_path / "cache", tmp_path / "cache" / ".." / "outside.json")


async def test_cancelled_write_finishes_before_clear(tmp_path, pages, monkeypatch):
    cache = JsonCache(tmp_path, "arknights-endfield", {"characters"})
    data = parse_characters(
        Document(pages["characters"], "https://www.prydwen.gg/arknights-endfield/characters", CAPTURE_TIME)
    )
    entered = threading.Event()
    release = threading.Event()
    original_write = cache_module.atomic_json

    def delayed_write(*args):
        entered.set()
        assert release.wait(3)
        original_write(*args)

    monkeypatch.setattr(cache_module, "atomic_json", delayed_write)
    writing = asyncio.create_task(cache.write("characters", data))
    clearing = None
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        writing.cancel()
        clearing = asyncio.create_task(clear_game_cache(tmp_path, "arknights-endfield", {"characters"}))
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(clearing), 0.05)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await writing
        await clearing
        assert not cache.path("characters").exists()
    finally:
        release.set()
        await asyncio.gather(*([writing, clearing] if clearing else [writing]), return_exceptions=True)
