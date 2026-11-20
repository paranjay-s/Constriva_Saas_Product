"""PLAN3D_AI_POLISH (plan3d/polish.py): the AI's answer is validated data. A fake client: no
live model."""

import pytest

from app.modules.plan3d import polish


class FakeClient:
    def __init__(self, reply):
        self.reply, self.calls = reply, 0

    def generate_json(self, **kw):
        self.calls += 1
        assert len(kw["images"]) == 2 and "room_living" in kw["text"]
        return self.reply


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(polish, "CACHE", tmp_path)


STILLS = [("room_living", b"jpeg-1"), ("elevation_front", b"jpeg-2")]


def test_fixes_are_validated_and_clamped():
    reply = {
        "fixes": [
            {"name": "room_living", "ev": 3.0, "kelvin": 9000, "why": "too dark"},
            {"name": "elevation_front", "ev": 0.02},  # too small to matter
            {"name": "room_unknown", "ev": 0.5},  # not one of the stills
            {"name": "elevation_front", "ev": "lots"},
        ]
    }
    client = FakeClient(reply)
    got = polish.fixes(STILLS, client)
    assert got == {"room_living": {"ev": 1.5, "kelvin": 6500, "why": "too dark"}}
    # cached: the same pictures are never asked about twice
    assert polish.fixes(STILLS, client) == got and client.calls == 1


def test_nothing_to_polish():
    assert polish.fixes([], FakeClient({})) == {}
    assert polish.fixes(STILLS, FakeClient({"fixes": "no"})) == {}
