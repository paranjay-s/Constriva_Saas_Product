"""The engineering drawing must not change: PDF, SVG, PNG and DXF of the sample plans are
byte for byte what feat/pro wrote (run stamps blanked, see snapshot_util)."""

import json

import pytest

from tests.floorplan.snapshot_util import FORMATS, GOLDEN, SAMPLES, engineering_hash

HASHES = json.loads((GOLDEN / "engineering_hashes.json").read_text())


@pytest.mark.parametrize("name", SAMPLES)
@pytest.mark.parametrize("fmt", FORMATS)
def test_engineering_export_unchanged(name: str, fmt: str) -> None:
    assert engineering_hash(name, fmt) == HASHES[f"{name}.{fmt}"]
