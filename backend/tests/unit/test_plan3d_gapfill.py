"""The AI gap-filler (plan3d/gapfill.py) with a fake model and a fake PlanTo3D: no live model."""

import pytest

from app.modules.plan3d import gapfill

TYPES = ["bedroom", "living", "kitchen", "store", "passage", "majlis"]


def plan():
    return {
        "scale_pt_per_ft": 10.0,
        "wall_pt": 5.0,
        "scale_source": "labels",
        "floors": [
            {
                "name": "Ground",
                "origin_pt": [100.0, 600.0],
                "walls": [[0, 40, 0, 0.5, 0]],
                "openings": [],
                "rooms": [
                    {"label": "", "type": "room", "rects": [[0, 12, 0, 10]]},
                    {"label": "KITCHEN", "type": "kitchen", "rects": [[12, 24, 0, 10]]},
                    {"label": "3 12,40", "type": "multipurpose", "rects": [[24, 36, 0, 10]]},
                ],
            }
        ],
        "checks": [{"severity": "warning", "message": "an unlabelled space", "kind": "unlabelled"}],
    }


def test_feet_and_pixels_round_trip():
    fr = gapfill._frame(plan(), plan()["floors"][0])
    px = gapfill.to_px(fr, 12.0, 10.0)
    assert [round(v, 6) for v in gapfill.to_ft(fr, *px)] == [12.0, 10.0]


class FakeService:
    def __init__(self, cover):
        self.cover, self.asked = cover, []

    async def support(self, job_id, floor, segments):
        self.asked.append(segments)
        return self.cover[: len(segments)]


async def test_names_legend_supported_walls_and_suggestions():
    p = plan()
    fr = gapfill._frame(p, p["floors"][0])
    a, b = gapfill.to_px(fr, 12.0, 0.5), gapfill.to_px(fr, 12.0, 10.0)  # a wall on the drawing
    c, d = gapfill.to_px(fr, 30.0, 2.0), gapfill.to_px(fr, 30.0, 8.0)  # one it does not show
    reply = {
        "rooms": [
            {"floor": 0, "room_id": 0, "label": "LOBBY", "type": "passage", "confidence": 0.9},
            {"floor": 0, "room_id": 1, "label": "BEDROOM", "type": "bedroom", "confidence": 0.95},
            {"floor": 0, "room_id": 9, "label": "X", "type": "store", "confidence": 0.9},
        ],
        "legend": [{"number": "3", "name": "MAJLIS"}],
        "walls": [
            {
                "floor": 0,
                "from": list(a),
                "to": list(b),
                "reason": "lobby partition",
                "confidence": 0.8,
            },
            {"floor": 0, "from": list(c), "to": list(d), "reason": "maybe", "confidence": 0.8},
        ],
        "openings": [{"floor": 0, "kind": "door", "at": list(a), "confidence": 0.7}],
        "scale": None,
    }
    svc = FakeService([0.9, 0.1])
    done = await gapfill.apply(p, reply, TYPES, svc, "j", classify=lambda n: n.lower())
    rooms = p["floors"][0]["rooms"]
    assert (
        rooms[0]["label"] == "LOBBY" and rooms[0]["type"] == "passage" and rooms[0]["src"] == "ai"
    )
    assert rooms[1]["label"] == "KITCHEN"  # a named room is never renamed
    assert rooms[2]["label"] == "MAJLIS" and rooms[2]["type"] == "majlis"  # from the legend
    assert done == {"rooms": 1, "legend": 1, "walls": 1, "suggestions": 2}
    added = p["floors"][0]["walls"][-1]
    assert abs((added[0] + added[1]) / 2 - 12.0) < 0.01 and abs(added[3] - added[2] - 9.5) < 0.01
    kinds = [c["kind"] for c in p["checks"]]
    assert kinds.count("ai_suggestion") == 2 and "unlabelled" in kinds


async def test_runs_once_and_survives_a_plan_without_a_frame(monkeypatch):
    saved = {}

    class Svc(FakeService):
        async def plan(self, job_id):
            q = plan()
            q["floors"][0].pop("origin_pt")
            return q

        async def room_types(self):
            return TYPES

        async def page_png(self, job_id):
            return b"png"

        async def save_plan(self, job_id, p):
            saved["plan"] = p

    reply = {"rooms": [], "legend": [], "openings": [],
             "walls": [{"floor": 0, "from": [1, 2], "to": [3, 4], "confidence": 0.9}]}  # fmt: skip
    gapfill._done.discard("j2")
    done = await gapfill.run(
        "j2", Svc([]), ask_fn=lambda p, page, types: reply, classify=lambda n: None
    )
    assert (
        done["walls"] == 0 and done["suggestions"] == 1
    )  # no frame: the wall is only a suggestion
    assert await gapfill.run("j2", Svc([])) == {}


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(gapfill, "CACHE", tmp_path)
