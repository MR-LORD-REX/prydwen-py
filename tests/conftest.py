import gzip
import json
from pathlib import Path

import pytest

from prydwen.games.endfield.parsers.builds import parse_character_build
from prydwen.parsing.document import Document
from tests.helpers import CAPTURE_TIME, FakeTransport


@pytest.fixture(scope="session")
def pages() -> dict[str, str]:
    root = Path(__file__).parent / "fixtures" / "endfield"
    return {path.stem: path.read_text(encoding="utf-8") for path in root.glob("*.html")}


@pytest.fixture
def transport(pages: dict[str, str]) -> FakeTransport:
    return FakeTransport(pages)


@pytest.fixture(scope="session")
def build_manifest():
    root = Path(__file__).parent / "fixtures" / "endfield" / "character_builds"
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def build_pages(build_manifest):
    root = Path(__file__).parent / "fixtures" / "endfield" / "character_builds"
    return {
        entry["identifier"]: gzip.decompress((root / entry["fixture"]).read_bytes()).decode("utf-8")
        for entry in build_manifest
    }


@pytest.fixture(scope="session")
def build_outputs(build_manifest, build_pages):
    return {
        entry["identifier"]: parse_character_build(
            Document(
                build_pages[entry["identifier"]],
                entry["url"],
                CAPTURE_TIME,
            )
        )
        for entry in build_manifest
    }
