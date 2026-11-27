# prydwen-py

An async Python library for Prydwen guide data, starting with **Arknights: Endfield**. It fetches public HTML, parses the rendered content and embedded catalog metadata, and returns Pydantic v2 models with asset URLs.

Requires Python 3.11+. The initial version is under development; install it from this checkout:

```console
python -m pip install -e .
```

```python
import asyncio

from prydwen import Prydwen


async def main():
    async with Prydwen.Endfield() as endfield:
        characters = await endfield.characters()
        print(characters.total_count)
        print(characters.characters[0].name)

        pieces = await endfield.list_gears()
        piece = await endfield.gear(pieces[0].identifier)
        print(piece.name, piece.assets.icon)

        sets = await endfield.list_gear_sets()
        gear_set = await endfield.gear_set(sets[0].identifier)
        print(gear_set.name, gear_set.total_count)

        banners = await endfield.current_banners("character", region="asia")
        codes = await endfield.redeem_codes()
        print(banners.total_count, codes.total_count)


asyncio.run(main())
```

## Endfield methods

- `list_characters()`, `list_weapons()`, `list_gears()`, `list_gear_sets()` return lists of name/identifier models.
- `characters()` returns `AllCharacters` with `.characters` and `.total_count`.
- `gear(identifier)` returns a specific `Gear`; `gear_set(identifier)` returns a `GearSet` with `.gears`, `.bonuses`, and `.total_count`.
- `banners()`, `current_banners()`, and `upcoming_banners()` accept `banner_type="both"`, `"character"`, or `"weapon"`. Upcoming includes teased entries.
- `redeem_codes()` returns currently source-listed active codes and rewards, applying known expiry at read time.
- `tier_list()` preserves each character's role/form placements. `team_tier_list()` preserves grouped teammate alternatives.

Every data method accepts keyword-only `force_new=False`. The default cache is **`<cwd>/.prywen_cache/arknights-endfield/`**, including that exact spelling. A missing/corrupt cache or `force_new=True` fetches the selected section. Valid caches have no automatic TTL. Collection results include `.source`, `.diagnostics`, and `.delivery` provenance.

```python
async with Prydwen.Endfield() as endfield:
    fresh = await endfield.characters(force_new=True)

await Prydwen.clear_cache("arknights-endfield", resource="characters")
```

Requests use aiohttp and switch to a serialized cloudscraper worker for recognized Cloudflare challenges. The default request interval is 10 seconds. Cache hits do not make network requests. Challenges requiring interactive verification raise a typed error.

Character summaries do not include detail-page builds or skills yet. Source omissions remain unknown; contradictory banner dates are preserved with diagnostics. Images are returned as URLs rather than downloaded. This library is an independent project; source content and artwork belong to their respective owners.

## Documentation and development

The [documentation](docs/index.md) covers installation, examples, every method, output models, cache behavior, and adding games. Its section structure follows the SKPort documentation layout and builds as a static GitHub Pages site.

```console
python -m pip install -e ".[dev,docs]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m mkdocs build --strict
python -m build
```

Normal tests use minimized captured HTML and fake transports. Enable external requests explicitly with `python -m pytest -m live tests/live`. See [CONTRIBUTING.md](CONTRIBUTING.md) for maintenance and [the publishing guide](docs/maintainers/publishing.md) for GitHub Pages setup. A project license has not been selected.
