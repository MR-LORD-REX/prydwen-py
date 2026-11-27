# Testing

```console
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m mkdocs build --strict
python -m build
```

Unit tests parse captured source HTML and test explicit stat, date, asset, and error semantics. Integration tests invoke all public methods using an injected fake transport, check cache round trips and forced refreshes, and verify expired data is filtered at read time.

Fixtures live in `tests/fixtures/endfield/`. Each has a URL, capture date, original document hash, fixture hash, and transformation note in `manifest.json`. The fixture rewrite retains semantic source DOM, removes SVG geometry, and reframes literal inline data across short script chunks. All records remain available for identity/count regression checks.

Counts are fixture expectations, not live assumptions. Tests should also cover representative source values and grouping boundaries so a parser cannot pass by returning records with empty fields.

## Character guide fixtures

`tests/fixtures/endfield/character_builds/` contains deterministic gzip captures for all 36 characters inspected on November 27, 2026, with a separate provenance manifest. These retain the Review, Build, and Teams DOM, literal guide properties, and the relevant equipment/character catalogs. Kit details, navigation, and SVG drawing geometry are omitted. The manifest records both compressed and decompressed fixture hashes.

The regression suite checks every captured character's build/team/rotation counts, model round trips, unavailable sections, and concise output against its full model. It allows changes only to designated prose fields and the `detailed` flag; every chart, action, comparison, link, highlighted phrase, and collection length must remain equal. Representative cases cover pie rounding and zero slices, timed calibration, actorless instructions, implicit page owners, flexible rosters, grouped replacements, duplicate kit slots, setless loadouts, and unequipped baselines.

Integration tests check that both detail modes share a full persistent guide, forced refresh affects one character, failed refreshes preserve old data, simultaneous modes share one request, and group clearing invalidates a pending write. The opt-in live guide check uses Si and verifies concise cache reuse.

## Live checks

```console
python -m pytest -m live tests/live
```

Live tests make external requests, use a temporary cache, and may fail when the source changes or requests encounter an unresolved challenge. They are excluded from the default test run. CI remains offline and does not crawl the site.
