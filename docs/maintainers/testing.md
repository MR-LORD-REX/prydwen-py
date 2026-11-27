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

## Live checks

```console
python -m pytest -m live tests/live
```

Live tests make external requests, use a temporary cache, and may fail when the source changes or requests encounter an unresolved challenge. They are excluded from the default test run. CI remains offline and does not crawl the site.
