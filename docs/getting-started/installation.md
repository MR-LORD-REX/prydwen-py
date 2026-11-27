# Installation

Use Python **3.11 or newer**. From a checkout of this repository:

```console
python -m venv .venv
python -m pip install -e .
```

Activate the environment before installation if your shell does not already select it. On Windows, activation is `.venv\Scripts\Activate.ps1`; on Linux/macOS use `source .venv/bin/activate`.

The distribution is named `prydwen-py`; the import is `prydwen`. A PyPI release has not been published as part of this implementation.

Runtime dependencies are aiohttp, cloudscraper, Beautiful Soup, lxml, and Pydantic v2. Browser automation is not required. Development and documentation extras are separate:

```console
python -m pip install -e ".[dev,docs]"
```

Verify the import:

```console
python -c "from prydwen import Prydwen; print(Prydwen.Endfield)"
```
