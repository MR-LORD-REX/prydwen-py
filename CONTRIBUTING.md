# Contributing

Use Python 3.11 or newer and install the development dependencies:

```console
python -m pip install -e ".[dev,docs]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m mkdocs build --strict
python -m build
```

Keep game parsers separate from client methods. Parsers accept a `Document`, perform no I/O, and return Pydantic datasets. Required identity/structure failures raise `UpstreamSchemaError`; optional source gaps produce diagnostics.

When a source page changes, update the smallest affected parser and captured fixture. Record source URL, capture date, original hash, and fixture transformation in `tests/fixtures/endfield/manifest.json`. Retain only relevant HTML and literal data frames; exclude ads, credentials, cookies, or challenge responses. Test representative values and relationship boundaries as well as fixture counts. Network requests belong only in opt-in `live` tests.

Public methods need Args, Returns, and Raises docstrings. Parser functions and meaningful internal helpers need docstrings explaining their extraction or normalization. Update the API reference and changelog with behavioral changes.

See [the architecture guide](docs/maintainers/architecture.md) for adding another game and [publishing](docs/maintainers/publishing.md) for the documentation workflow. Choose a project license before distributing a public release.
