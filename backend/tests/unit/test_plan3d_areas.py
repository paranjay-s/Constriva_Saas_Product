"""Unknown labels classified by one AI call per plan (plan3d/areas.py), with a fake client:
no live model."""

import pytest

from app.modules.plan3d import areas

TYPES = ["bedroom", "living", "store", "garden", "pool"]
HELIPAD = {"type": "helipad", "name": "Helipad", "surface": "concrete", "edge": "kerb",
           "height": {"mode": "flat", "value_m": 0}, "walkable": True,
           "markings": [{"kind": "text", "at": [0.5, 0.5], "text": "H", "size_m": 4}], "objects": []}  # fmt: skip


class FakeClient:
    provider, model, last_usage = "fake", "fake", None

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(self, *, system_prompt, images, text, json_schema=None):
        self.calls += 1
        assert "HELIPAD" in text and "Types: bedroom" in text
        return {"labels": [
            {"label": "HELIPAD", "type": "new", "confidence": 0.9, "spec": HELIPAD},
            {"label": "BOX ROOM", "type": "store", "confidence": 0.7},
            {"label": "MYSTERY", "type": "spaceship", "confidence": 0.9},     # not one of ours
            {"label": "NOT ASKED", "type": "store", "confidence": 0.9},       # not asked about
        ]}  # fmt: skip


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(areas, "CACHE", tmp_path)
    return tmp_path


def test_one_call_classifies_every_label_and_is_cached(cache):
    client = FakeClient()
    got = areas.classify_labels(["HELIPAD", "BOX ROOM", "MYSTERY", "HELIPAD"], TYPES, client)
    assert client.calls == 1
    assert got["HELIPAD"] == {"type": "new", "confidence": 0.9, "spec": HELIPAD}
    assert got["BOX ROOM"] == {"type": "store", "confidence": 0.7}
    assert "MYSTERY" not in got and "NOT ASKED" not in got
    again = areas.classify_labels(["box room", "mystery", "helipad"], TYPES, client)  # same set
    assert client.calls == 1 and again.keys() == {"box room", "helipad"}


def test_no_labels_no_call(cache):
    client = FakeClient()
    assert areas.classify_labels(["", "  "], TYPES, client) == {} and client.calls == 0
