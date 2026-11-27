# Assets and stats

Models return observed URLs, not downloaded image bytes. `EntityAssets` has optional `.icon`, `.card`, `.portrait`, and `.background` links. Each `AssetLink` contains `.url`, optional `.alt`, `.width`, and `.height`.

```python
async with Prydwen.Endfield() as endfield:
    result = await endfield.characters()
    for character in result.characters:
        if character.assets.icon is not None:
            print(str(character.assets.icon.url))
```

Missing variants are `None`; the parser does not guess filenames. Pydantic `HttpUrl` values can be converted to strings for image libraries. Team backgrounds, banner art, chip icons, and code reward icons are kept in their corresponding models.

## Explicit stat units

Gear stats and weapon boosts retain `.label`, `.raw_value`, `.value`, `.unit`, `.target`, and optional `.stat_id`. Numeric values use `Decimal`; percent values use fractions. For example, source `26.00%` becomes Decimal `0.2600`, unit `fraction`, display `26.00%`.

```python
async with Prydwen.Endfield() as endfield:
    piece = await endfield.gear((await endfield.list_gears())[0].identifier)
    for stat in piece.stats:
        print(stat.label, stat.display, stat.stat_id)
```

Property IDs follow the verified concepts in the [SKPort stat reference](https://github.com/MR-LORD-REX/skport-py/blob/8e4d35d7615f437f6d2be4e947ac670e2451bd31/src/skport/games/endfield/models/stats.py). This library has no SKPort dependency and does not calculate combat stats. Unknown labels keep their values and get an `unmapped_stat` diagnostic. Main/Secondary Attribute remain conditional targets rather than being rewritten into a character attribute.

Display contexts matter: the source shows different passive boost ranks for high-rarity weapons, and gear has its own displayed level. Values do not imply unshown level progression. An absent property is unknown, not zero.

Use `model_dump(mode="json")` or `model_dump_json()` for rendering pipelines. Decimal values serialize as strings. Cache serialization excludes computed display/count fields and runtime delivery information so round trips validate correctly.
