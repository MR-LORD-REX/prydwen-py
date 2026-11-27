import asyncio
import json

import pytest

from prydwen import Prydwen
from prydwen.core.transport import FetchedPage
from prydwen.exceptions import NetworkError, NotFoundError, UpstreamSchemaError
from tests.helpers import CAPTURE_TIME, FakeTransport


@pytest.fixture
def build_transport(pages, build_pages):
    return FakeTransport({**pages, **build_pages})


async def test_character_build_modes_share_full_persistent_cache(build_transport, tmp_path):
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=build_transport) as client:
        compact = await client.character_build("si", detailed=False)
        assert not compact.detailed and not compact.delivery.from_cache
        full = await client.character_build("si")
        assert full.detailed and full.delivery.from_cache
        assert compact.calculations.charts == full.calculations.charts
        assert compact.teams[0].rotations == full.teams[0].rotations
        assert compact.weapons[0].explanation != full.weapons[0].explanation
        full.teams.clear()
        assert len((await client.character_build("si")).teams) == 4
    assert len(build_transport.calls) == 2
    path = tmp_path / "arknights-endfield" / "character_builds" / "si.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["data"]["detailed"] is True
    assert payload["resource"] == "character_builds/si"
    metadata = json.loads((path.parents[1] / "metadata.json").read_text())
    assert metadata["resources"]["character_builds/si"]["identifiers"] == [{"identifier": "si", "name": "Si"}]
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=build_transport) as client:
        cached = await client.character_build("si", False)
        assert cached.delivery.from_cache and not cached.detailed
    assert len(build_transport.calls) == 2


async def test_refresh_only_retrieves_requested_character(build_transport, tmp_path):
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=build_transport) as client:
        await client.character_build("si")
        await client.character_build("arclight")
        fresh = await client.character_build("si", False, force_new=True)
        assert not fresh.delivery.from_cache and not fresh.detailed
    assert [url.rsplit("/", 1)[-1] for url in build_transport.calls] == ["characters", "si", "arclight", "si"]


async def test_failed_refresh_keeps_full_guide_cache(build_transport, tmp_path):
    path = tmp_path / "arknights-endfield" / "character_builds" / "si.json"
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=build_transport) as client:
        await client.character_build("si")
        original = path.read_bytes()
        build_transport.error = NetworkError("offline")
        with pytest.raises(NetworkError, match="offline"):
            await client.character_build("si", force_new=True)
        assert path.read_bytes() == original
        build_transport.error = None
        build_transport.pages["si"] = "<html>Changed markup</html>"
        with pytest.raises(UpstreamSchemaError):
            await client.character_build("si", force_new=True)
        assert path.read_bytes() == original
        assert (await client.character_build("si")).delivery.from_cache


async def test_missing_and_corrupt_entity_caches_refetch(build_transport, tmp_path):
    path = tmp_path / "arknights-endfield" / "character_builds" / "si.json"
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=build_transport) as client:
        await client.character_build("si")
        path.write_text("{broken", encoding="utf-8")
        assert not (await client.character_build("si")).delivery.from_cache
    assert len(build_transport.calls) == 3


async def test_concurrent_character_build_calls_coalesce(build_transport, tmp_path):
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=build_transport) as client:
        await client.characters()
        build_transport.release = asyncio.Event()
        build_transport.started.clear()
        tasks = [asyncio.create_task(client.character_build("si", bool(index % 2))) for index in range(6)]
        await asyncio.wait_for(build_transport.started.wait(), timeout=5)
        assert len(build_transport.calls) == 2
        build_transport.release.set()
        results = await asyncio.gather(*tasks)
        assert [output.detailed for output in results] == [False, True, False, True, False, True]
        assert len(build_transport.calls) == 2


async def test_clear_build_group_retains_catalog_and_invalidates_inflight_write(build_transport, tmp_path):
    root = tmp_path / "arknights-endfield"
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=build_transport) as client:
        await client.character_build("si")
        await client.character_build("arclight")
        build_transport.release = asyncio.Event()
        build_transport.started.clear()
        refreshing = asyncio.create_task(client.character_build("si", force_new=True))
        await build_transport.started.wait()
        await Prydwen.clear_cache(resource="character_builds", cache_dir=tmp_path)
        assert not (root / "character_builds").exists()
        assert (root / "characters.json").exists()
        build_transport.release.set()
        await refreshing
        assert not (root / "character_builds").exists()
        await client.character_build("si")
        assert (root / "character_builds" / "si.json").exists()


@pytest.mark.parametrize(
    "identifier", ["", "Si", "../si", "/si", "si?x=1", "si/other", "https://evil.example"]
)
async def test_invalid_character_identifiers_do_not_request(identifier, build_transport, tmp_path):
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=build_transport) as client:
        with pytest.raises(ValueError):
            await client.character_build(identifier)
    assert not build_transport.calls


async def test_unknown_and_invalid_arguments_are_typed(build_transport, tmp_path):
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=build_transport) as client:
        for kwargs in [{"detailed": "false"}, {"force_new": 1}]:
            with pytest.raises(TypeError):
                await client.character_build("si", **kwargs)
        assert not build_transport.calls
        with pytest.raises(NotFoundError):
            await client.character_build("missing-character")
    assert len(build_transport.calls) == 1


async def test_redirected_other_character_does_not_replace_cache(pages, build_pages, tmp_path):
    class RedirectingTransport(FakeTransport):
        redirect = False

        async def fetch(self, url):
            if self.redirect and url.endswith("/si"):
                self.calls.append(url)
                return FetchedPage(build_pages["akekuri"], url.removesuffix("si") + "akekuri", CAPTURE_TIME)
            return await super().fetch(url)

    transport = RedirectingTransport({**pages, **build_pages})
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=transport) as client:
        await client.character_build("si")
        path = tmp_path / "arknights-endfield" / "character_builds" / "si.json"
        original = path.read_bytes()
        transport.redirect = True
        with pytest.raises(UpstreamSchemaError, match="requested identifier"):
            await client.character_build("si", force_new=True)
        assert path.read_bytes() == original
