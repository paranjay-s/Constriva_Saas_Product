"""Unknown labels classified by one AI call per plan (plan3d/areas.py), with a fake client:
no live model."""

import pytest

from app.modules.plan3d import areas

TYPES = ["bedroom", "living", "store", "garden", "pool"]
HELIPAD = {"type": "helipad", "name": "Helipad", "surface": "concrete", "edge": "kerb",
           "height": {"mode": "flat", "value_m": 0}, "walkable": True,
           "markings": [{"kind": "text", "at": [0.5, 0.5], "text": "H", "size_m": 4}],
           "objects": []}  # fmt: skip


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


class FakeService:
    """PlanTo3D as type_unknown_rooms sees it: a plan, its room types, the area library."""

    def __init__(self, plan) -> None:
        self._plan, self.saved, self.areas = plan, None, []

    async def plan(self, job_id):
        return self._plan

    async def room_types(self):
        return TYPES

    async def save_area(self, spec):
        if spec.get("surface") not in ("concrete",):
            raise ValueError("refused")
        self.areas.append(spec)
        return spec["type"]

    async def save_plan(self, job_id, plan):
        self.saved = plan


async def test_unknown_rooms_get_a_type_or_a_new_area_once():
    plan = {"floors": [{"rooms": [
        {"type": "multipurpose", "label": "HELIPAD"},
        {"type": "multipurpose", "label": "BOX ROOM"},
        {"type": "multipurpose", "label": "ODD"},
        {"type": "bedroom", "label": "BEDROOM"}]}]}  # fmt: skip
    answers = {"HELIPAD": {"type": "new", "confidence": 0.9, "spec": HELIPAD},
               "BOX ROOM": {"type": "store", "confidence": 0.7},
               "ODD": {"type": "store", "confidence": 0.3}}  # fmt: skip
    svc = FakeService(plan)
    areas._typed.discard("j1")
    n = await areas.type_unknown_rooms("j1", svc, classify=lambda labels, types: answers)
    rooms = svc.saved["floors"][0]["rooms"]
    assert n == 2
    assert rooms[0]["type"] == "custom" and rooms[0]["area_type"] == "helipad"
    assert rooms[0]["src"] == "ai"
    assert rooms[1]["type"] == "store"
    assert rooms[2]["type"] == "multipurpose"  # too unsure: stays flagged
    again = await areas.type_unknown_rooms("j1", svc, classify=lambda labels, types: answers)
    assert again == 0
