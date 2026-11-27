import pytest

from prydwen import Prydwen


@pytest.mark.live
async def test_live_characters_refresh_and_cache(tmp_path):
    async with Prydwen.Endfield(cache_dir=tmp_path, timeout=45) as client:
        result = await client.characters(force_new=True)
        assert result.total_count > 0
        assert all(character.identifier and character.name for character in result.characters)
        assert not result.delivery.from_cache
        cached = await client.characters()
        assert cached.delivery.from_cache
        assert cached.characters == result.characters


@pytest.mark.live
async def test_live_remaining_sections(tmp_path):
    async with Prydwen.Endfield(cache_dir=tmp_path, timeout=45) as client:
        assert await client.list_weapons(force_new=True)
        pieces = await client.list_gears(force_new=True)
        sets = await client.list_gear_sets()
        assert pieces and sets
        assert (await client.gear(pieces[0].identifier)).name == pieces[0].name
        assert (await client.gear_set(sets[0].identifier)).gears
        assert (await client.banners(force_new=True)).banners
        assert (await client.tier_list(force_new=True)).tiers
        assert (await client.team_tier_list(force_new=True)).tiers
        codes = await client.redeem_codes(force_new=True)
        assert all(code.code for code in codes.codes)
