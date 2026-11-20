"""C3.1: curved walls, round rooms and spiral stairs, from the building model to the drawing, to
the PlanTo3D plan, and back from the drawing alone through PlanTo3D's vector detector."""

import json
import math
import subprocess
from pathlib import Path

import pymupdf
import pytest

from app.modules.ai.floorplan.model.build import build_building
from app.modules.ai.floorplan.model.building import ArcWall, Room
from app.modules.ai.floorplan.model.planto3d import to_planto3d
from app.modules.ai.floorplan.render.exports import export_plan
from tests.floorplan.snapshot_util import sample_plan

ROOT = Path(__file__).resolve().parents[3]
DETECT = ROOT / "services" / "planto3d" / "detect.py"
FT = 304.8


def _with_rotunda(name: str = "nandu"):
    """a sample villa with a round room (a full circle of curved wall) inside its living room and
    its stair made spiral"""
    plan = sample_plan(name)
    b = build_building(plan)
    st = b.storeys[0]
    living = next(r for r in st.rooms if r.type == "living")
    xs, ys = [p[0] for p in living.polygon], [p[1] for p in living.polygon]
    cx, cy = (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2
    r_in = min(max(xs) - min(xs), max(ys) - min(ys)) // 2 - 700
    t = 150
    st.arcs.append(ArcWall(id="AW1", center=(cx, cy), radius=r_in + t // 2, thickness=t))
    poly = [
        (round(cx + r_in * math.cos(math.radians(a))), round(cy + r_in * math.sin(math.radians(a))))
        for a in range(0, 360, 10)
    ]
    st.rooms.append(
        Room(id="R-ROT", name="ROTUNDA", type="living", zone="public", polygon=poly,
             circle=(cx, cy, r_in), net_area_m2=round(math.pi * r_in**2 / 1e6, 2))
    )
    for s in st.stairs:
        s.shape = "spiral"
    return plan, b, (cx, cy, r_in, t)


def test_the_model_keeps_curves_only_when_there_are_some() -> None:
    plain = build_building(sample_plan("nandu")).to_json_dict()
    assert "arcs" not in plain["storeys"][0]
    assert all("circle" not in r for r in plain["storeys"][0]["rooms"])
    _, b, _ = _with_rotunda()
    data = b.to_json_dict()["storeys"][0]
    assert data["arcs"][0]["radius"] > 0 and data["rooms"][-1]["circle"]


def test_the_planto3d_plan_carries_the_arc_the_round_room_and_the_spiral() -> None:
    _, b, (cx, cy, r_in, t) = _with_rotunda()
    floor = to_planto3d(b)["floors"][0]
    (arc,) = floor["arcs"]
    assert arc["r"] == pytest.approx((r_in + t / 2) / FT, abs=0.01)
    assert (arc["a0"], arc["a1"]) == (0.0, 360.0)
    room = next(r for r in floor["rooms"] if r["label"] == "ROTUNDA")
    assert room["circle"][2] == pytest.approx(r_in / FT, abs=0.01)
    # row slices of the disc, all inside it
    for q in room["rects"]:
        for x in (q[0], q[1]):
            for y in (q[2], q[3]):
                assert math.hypot(x - room["circle"][0], y - room["circle"][1]) <= room["circle"][2] + 0.01
    assert all(s.get("shape") == "spiral" for s in floor["stairs"])


def test_the_drawing_shows_the_curves() -> None:
    plan, b, _ = _with_rotunda()
    svg = export_plan(plan, "svg", building=b).data.decode()
    pdf = export_plan(plan, "pdf", building=b).data
    assert "ROTUNDA" in svg and pymupdf.open(stream=pdf, filetype="pdf").page_count == 1


@pytest.mark.skipif(not Path("/usr/bin/python3").exists(), reason="PlanTo3D runs on /usr/bin/python3")
def test_the_detector_reads_the_curved_wall_and_the_round_room_back(tmp_path) -> None:
    plan, b, (cx, cy, r_in, t) = _with_rotunda()
    pdf = export_plan(plan, "pdf", building=b).data
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:  # the drawing only: no model attached
        for n in list(doc.embfile_names()):
            doc.embfile_del(n)
        (tmp_path / "plan.pdf").write_bytes(doc.tobytes())
    out = tmp_path / "plan.json"
    run = subprocess.run(
        ["/usr/bin/python3", str(DETECT), str(tmp_path / "plan.pdf"), str(out)],
        cwd=DETECT.parent, capture_output=True, text=True, timeout=240, check=False,
    )
    assert run.returncode == 0, run.stderr[-2000:]
    floor = max(json.loads(out.read_text())["floors"], key=lambda f: len(f["walls"]))
    arcs = floor.get("arcs") or []
    assert len(arcs) == 1, arcs
    assert arcs[0]["r"] == pytest.approx((r_in + t / 2) / FT, rel=0.05)
    assert arcs[0]["a1"] - arcs[0]["a0"] == pytest.approx(360.0)
    rounds = [r for r in floor["rooms"] if r.get("circle")]
    assert len(rounds) == 1 and rounds[0]["circle"][2] == pytest.approx(r_in / FT, rel=0.08)
