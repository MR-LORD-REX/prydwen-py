import asyncio
import json
from datetime import UTC, datetime

import pytest

from prydwen import Prydwen
from prydwen.exceptions import ClientClosedError, NetworkError, NotFoundError, UpstreamSchemaError
from tests.helpers import CAPTURE_TIME


@pytest.mark.asyncio
async def test_public_batch_uses_seven_resources(transport, tmp_path, monkeypatch):
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=transport) as client:
        monkeypatch.setattr(client, "_now", lambda: CAPTURE_TIME)
        assert len(await client.list_characters()) == 36
        assert len(await client.list_weapons()) == 87
        pieces = await client.list_gears()
        sets = await client.list_gear_sets()
        assert len(pieces) == 202 and len(sets) == 17
        assert (await client.characters()).total_count == 36
        assert (await client.gear(pieces[0].identifier)).name == pieces[0].name
        gear_set = await client.gear_set(sets[0].identifier)
        assert gear_set.total_count == len(gear_set.gears) > 0
        assert (await client.banners()).total_count == 17
        assert (await client.current_banners()).total_count == 6
        assert (await client.upcoming_banners()).total_count == 11
        assert (await client.redeem_codes()).total_count == 4
        assert (await client.tier_list()).total_count == 38
        assert (await client.team_tier_list()).total_count == 15
    assert len(transport.calls) == 7
    metadata = json.loads((tmp_path / "arknights-endfield" / "metadata.json").read_text(encoding="utf-8"))
    assert len(metadata["resources"]) == 7
    assert len(metadata["resources"]["characters"]["paths"]) == 36


async def test_cwd_root_is_captured_without_eager_io(transport, tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.chdir(first)
    client = Prydwen.Endfield(transport=transport)
    assert not (first / ".prywen_cache").exists()
    monkeypatch.chdir(second)
    async with client:
        await client.characters()
    assert (first / ".prywen_cache" / "arknights-endfield" / "characters.json").exists()
    assert not (second / ".prywen_cache").exists()


async def test_cache_hits_refresh_and_new_client(transport, tmp_path):
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=transport) as client:
        first = await client.characters()
        second = await client.characters()
        fresh = await client.characters(force_new=True)
        assert not first.delivery.from_cache and second.delivery.from_cache
        assert first.source == second.source
        assert not fresh.delivery.from_cache
    assert len(transport.calls) == 2
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=transport) as other:
        cached = await other.characters()
        assert cached.delivery.from_cache
        cached.characters.clear()
        assert (await other.characters()).total_count == 36
    assert len(transport.calls) == 2


async def test_failed_forced_fetch_or_parse_preserves_good_cache(transport, tmp_path):
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=transport) as client:
        await client.characters()
        cache = tmp_path / "arknights-endfield" / "characters.json"
        original = cache.read_bytes()
        transport.error = NetworkError("offline")
        with pytest.raises(NetworkError, match="offline"):
            await client.characters(force_new=True)
        assert cache.read_bytes() == original
        transport.error = None
        transport.pages["characters"] = "<html>Unexpected page</html>"
        with pytest.raises(UpstreamSchemaError):
            await client.characters(force_new=True)
        assert cache.read_bytes() == original
        assert (await client.characters()).total_count == 36


@pytest.mark.parametrize(
    "corruption", ["invalid-json", "checksum", "schema", "wrong-resource", "wrong-source"]
)
async def test_incompatible_cache_refetches(corruption, transport, tmp_path):
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=transport) as client:
        await client.characters()
        cache = tmp_path / "arknights-endfield" / "characters.json"
        if corruption == "invalid-json":
            cache.write_text("{", encoding="utf-8")
        else:
            entry = json.loads(cache.read_text(encoding="utf-8"))
            key, value = {
                "checksum": ("payload_sha256", "bad"),
                "schema": ("cache_schema_version", 999),
                "wrong-resource": ("resource", "weapons"),
                "wrong-source": ("source_url", "https://example.com"),
            }[corruption]
            entry[key] = value
            cache.write_text(json.dumps(entry), encoding="utf-8")
        assert not (await client.characters()).delivery.from_cache
        assert len(transport.calls) == 2


@pytest.mark.parametrize("forced", [False, True])
async def test_concurrent_initial_calls_share_one_fetch(forced, transport, tmp_path):
    transport.release = asyncio.Event()
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=transport) as client:
        tasks = [asyncio.create_task(client.characters(force_new=forced)) for _ in range(6)]
        await transport.started.wait()
        transport.release.set()
        results = await asyncio.gather(*tasks)
        assert all(result.total_count == 36 for result in results)
        assert len(transport.calls) == 1


async def test_shared_gear_cache_and_missing_identifiers(transport, tmp_path):
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=transport) as client:
        duplicate = [entry for entry in await client.list_gears() if entry.name == "AIC Fieldwork Flashlight"]
        assert len(duplicate) == 2
        assert (await client.gear(duplicate[0].identifier)).identifier != (
            await client.gear(duplicate[1].identifier)
        ).identifier
        for method in (client.gear, client.gear_set):
            with pytest.raises(NotFoundError):
                await method("not-a-known-identifier")
        assert len(transport.calls) == 1


async def test_banner_filters_and_code_expiry_use_cached_data(transport, tmp_path, monkeypatch):
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=transport) as client:
        monkeypatch.setattr(client, "_now", lambda: CAPTURE_TIME)
        assert (await client.banners("weapon")).total_count == 5
        assert (await client.current_banners("character")).total_count == 2
        assert (await client.upcoming_banners("character")).total_count == 10
        assert (await client.redeem_codes()).total_count == 4
        monkeypatch.setattr(client, "_now", lambda: datetime(2028, 1, 1, tzinfo=UTC))
        assert (await client.redeem_codes()).total_count == 3
        current = await client.current_banners("character")
        assert current.total_count == 0
        assert len(transport.calls) == 2


async def test_invalid_inputs_and_client_lifecycle(transport, tmp_path):
    client = Prydwen.Endfield(cache_dir=tmp_path, transport=transport)
    with pytest.raises(ClientClosedError):
        await client.characters()
    async with client:
        with pytest.raises(ValueError):
            await client.banners("unknown")
        with pytest.raises(ValueError):
            await client.current_banners(region="unknown")
        with pytest.raises(ValueError):
            await client.gear("")
        with pytest.raises(TypeError):
            await client.characters(force_new=1)
        assert not transport.calls
    with pytest.raises(ClientClosedError):
        await client.characters()
    with pytest.raises(ClientClosedError):
        async with client:
            pass


async def test_scoped_clearing_and_metadata_repair(transport, tmp_path):
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=transport) as client:
        await client.characters()
        await client.list_weapons()
        metadata = tmp_path / "arknights-endfield" / "metadata.json"
        metadata.write_text("{}", encoding="utf-8")
        assert (await client.characters()).delivery.from_cache
        assert "characters" in json.loads(metadata.read_text(encoding="utf-8"))["resources"]
        await Prydwen.clear_cache(resource="characters", cache_dir=tmp_path)
        assert (tmp_path / "arknights-endfield" / "weapons.json").exists()
        assert not (tmp_path / "arknights-endfield" / "characters.json").exists()
        await client.characters()
        assert len(transport.calls) == 3
        await Prydwen.clear_cache(cache_dir=tmp_path)
        assert not (tmp_path / "arknights-endfield").exists()


async def test_clear_prevents_inflight_repopulation(transport, tmp_path):
    transport.release = asyncio.Event()
    async with Prydwen.Endfield(cache_dir=tmp_path, transport=transport) as client:
        task = asyncio.create_task(client.characters())
        await transport.started.wait()
        await Prydwen.clear_cache(resource="characters", cache_dir=tmp_path)
        transport.release.set()
        assert (await task).total_count == 36
        assert not (tmp_path / "arknights-endfield" / "characters.json").exists()


@pytest.mark.parametrize("kwargs", [{"game": "../elsewhere"}, {"resource": "../../elsewhere"}])
async def test_clear_rejects_arbitrary_paths(kwargs, tmp_path):
    with pytest.raises(ValueError):
        await Prydwen.clear_cache(cache_dir=tmp_path, **kwargs)
