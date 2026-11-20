"""The building model: grid, walls, areas, and the lossless PlanJSON / PlanTo3D exports."""

import pytest
from shapely.geometry import Polygon

from app.modules.ai.floorplan.model.build import build_building, mm
from app.modules.ai.floorplan.model.building import GRID_MM, Building
from app.modules.ai.floorplan.model.planjson import from_planjson, to_planjson
from app.modules.ai.floorplan.model.planto3d import MM_PER_FT, to_planto3d
from app.modules.ai.floorplan.pipeline.layout.engine import assemble
from app.modules.ai.floorplan.pipeline.layout.topology import Topology
from app.modules.ai.floorplan.schemas.plan import FloorPlan, Room
from app.modules.plans.schemas import PlanJSON


@pytest.fixture
def building(sample_plan: FloorPlan) -> Building:
    return build_building(sample_plan, date="2026-11-20")


def _pool_plan() -> FloorPlan:
    """A small house beside a pool and a garden, doors placed by code."""
    rooms = [
        Room(id="living_1", type="living", label="LIVING", x=0, y=600, w=600, h=600),
        Room(id="bed_1", type="bedroom", label="BED ROOM", x=600, y=600, w=420, h=420),
        Room(id="bath_1", type="bath", label="BATH", x=600, y=1020, w=420, h=180),
        Room(id="kitchen_1", type="kitchen", label="KITCHEN", x=0, y=1200, w=600, h=300),
        Room(id="stair_1", type="stair", label="STAIR", x=600, y=1200, w=420, h=300),
        Room(id="pool_1", type="pool", label="SWIMMING POOL", x=0, y=0, w=1020, h=600),
        Room(id="garden_1", type="garden", label="LAWN", x=1020, y=0, w=300, h=1500),
    ]
    from app.modules.ai.floorplan.schemas.plan import Meta, Plot

    plot = Plot(width=1320, depth=1500, road_side="south")
    topo = Topology(
        root="living_1",
        parent={
            "living_1": None,
            "bed_1": "living_1",
            "bath_1": "bed_1",
            "kitchen_1": "living_1",
            "stair_1": "kitchen_1",
            "pool_1": None,
            "garden_1": None,
        },
    )
    return assemble(rooms, topo, plot, Meta(), "plan_pool")


def _all_points(b: Building):
    for st in b.storeys:
        for w in st.walls:
            yield from (w.a, w.b)
        for r in st.rooms:
            yield from r.polygon
    for e in b.site.elements:
        yield from e.polygon


def test_every_coordinate_is_on_the_50_mm_grid(building: Building) -> None:
    for x, y in _all_points(building):
        assert x % GRID_MM == 0 and y % GRID_MM == 0, (x, y)


def test_walls_are_typed_with_the_set_thicknesses(building: Building) -> None:
    walls = building.storeys[0].walls
    assert {w.kind for w in walls} >= {"exterior", "interior", "partition"}
    for w in walls:
        assert w.thickness == {"exterior": 200, "interior": 150, "partition": 100}[w.kind]
        assert w.a < w.b  # walls run west->east or north->south


def test_room_gross_areas_add_up_to_the_built_up_area(building: Building) -> None:
    a = building.areas
    assert abs(a.rooms_gross_m2 - a.built_up_m2) <= 0.01 * a.built_up_m2
    assert a.built_up_net_m2 < a.built_up_m2
    assert abs(a.plot_m2 - (a.built_up_m2 + a.exterior_m2)) < 0.02
    for r in building.storeys[0].rooms:
        assert 0 < r.net_area_m2 < r.gross_area_m2


def test_every_door_and_window_sits_inside_its_wall(building: Building) -> None:
    st = building.storeys[0]
    for o in st.openings:
        w = st.wall(o.wall)
        assert o.width / 2 <= o.offset <= w.length - o.width / 2, o.id
    assert sum(o.main_entrance for o in st.openings) == 1


def test_planjson_round_trip_is_exact(building: Building) -> None:
    doc = to_planjson(building)
    PlanJSON.model_validate(doc)
    assert from_planjson(doc) == building


def test_planjson_round_trip_with_pool_and_stair() -> None:
    b = build_building(_pool_plan(), date="2026-11-20")
    assert b.storeys[0].stairs and any(e.kind == "pool" for e in b.site.elements)
    assert from_planjson(to_planjson(b)) == b
    lawn = [e for e in b.site.elements if e.kind == "lawn"]
    assert lawn, "a garden labelled LAWN is a lawn"


def test_planjson_offsets_are_to_the_opening_centre(building: Building) -> None:
    doc = to_planjson(building)
    walls = {w["id"]: w for w in doc["levels"][0]["walls"]}
    for o in doc["levels"][0]["openings"]:
        w = walls[o["wall_id"]]
        horizontal = w["start"][1] == w["end"][1]
        expect = (
            [w["start"][0] + o["offset"], w["start"][1]]
            if horizontal
            else [w["start"][0], w["start"][1] + o["offset"]]
        )
        assert o["position"] == pytest.approx(expect, abs=1e-6)


def _ft(v: float) -> float:
    return v / MM_PER_FT


def test_planto3d_keeps_every_wall_opening_room_and_flight() -> None:
    b = build_building(_pool_plan(), date="2026-11-20")
    p = to_planto3d(b)
    f = p["floors"][0]
    st = b.storeys[0]
    depth = b.site.depth
    assert f["size"] == pytest.approx([_ft(b.site.width), _ft(depth)], abs=1e-3)
    # walls: centre line and thickness recoverable, end points covered
    building_walls = [w for w in f["walls"] if w[4] == 0]
    assert len(building_walls) == len(st.walls)
    for w, r in zip(st.walls, building_walls, strict=True):
        x0, x1, y0, y1, _ = r
        if w.horizontal:
            assert (y1 - y0) == pytest.approx(_ft(w.thickness), abs=1e-3)
            assert (y0 + y1) / 2 == pytest.approx(_ft(depth - w.a[1]), abs=1e-3)
            assert x0 <= _ft(w.a[0]) + 1e-3 and x1 >= _ft(w.b[0]) - 1e-3
        else:
            assert (x1 - x0) == pytest.approx(_ft(w.thickness), abs=1e-3)
            assert (x0 + x1) / 2 == pytest.approx(_ft(w.a[0]), abs=1e-3)
    # openings: one per model opening, same width
    assert len(f["openings"]) == len(st.openings)
    for o, q in zip(st.openings, f["openings"], strict=True):
        x0, x1, y0, y1 = q["rect"]
        span = (x1 - x0) if q["axis"] == "x" else (y1 - y0)
        assert span == pytest.approx(_ft(o.width), abs=1e-3)
        assert q["type"] == o.kind
    # rooms: every model room and every site area, with the right type
    types = {r["id"]: r["type"] for r in f["rooms"]}
    for r in st.rooms:
        assert r.id in types
    assert types["stair_1"] == "stair"
    pool = next(r for r in f["rooms"] if r["type"] == "pool")
    assert "water" in pool
    # the pool and garden lie inside the floor's size (the plot)
    for r in f["rooms"]:
        for x0, x1, y0, y1 in r["rects"]:
            assert -1e-3 <= x0 <= x1 <= f["size"][0] + 1e-3
            assert -1e-3 <= y0 <= y1 <= f["size"][1] + 1e-3
    # site element areas are kept
    for e in b.site.elements:
        if e.kind in ("boundary_wall", "gate"):
            continue
        room = next(r for r in f["rooms"] if r["id"] == e.id)
        area = sum((x1 - x0) * (y1 - y0) for x0, x1, y0, y1 in room["rects"])
        assert area == pytest.approx(Polygon(e.polygon).area / MM_PER_FT**2, rel=1e-3)
    # stairs: every flight, the first one holds the UP word
    flights = [fl for s in st.stairs for fl in s.flights]
    assert len(f["stairs"]) == len(flights)
    assert f["stairs"][0]["words"][0][0] == "UP"
    assert sum(s["steps"] for s in f["stairs"]) == st.stairs[0].risers


def test_custom_labels_reach_3d_with_their_own_type() -> None:
    plan = _pool_plan()
    rooms = [
        r.model_copy(update={"type": "puja", "label": "PUJA"}) if r.id == "bed_1" else r
        for r in plan.rooms
    ]
    plan = plan.model_copy(update={"rooms": rooms})
    p = to_planto3d(build_building(plan))
    assert any(r["type"] == "puja" for r in p["floors"][0]["rooms"])


def test_mm_rounds_to_the_grid() -> None:
    assert mm(1113) == 11150 and mm(1112) == 11100 and mm(0) == 0
