from pathlib import Path

import pytest

from tests.helpers import FakeTransport


@pytest.fixture(scope="session")
def pages() -> dict[str, str]:
    root = Path(__file__).parent / "fixtures" / "endfield"
    return {path.stem: path.read_text(encoding="utf-8") for path in root.glob("*.html")}


@pytest.fixture
def transport(pages: dict[str, str]) -> FakeTransport:
    return FakeTransport(pages)
