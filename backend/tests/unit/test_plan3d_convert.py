"""PlanJSON -> PlanTo3D plan JSON (app/modules/plan3d/convert.py).

No model and no network: the plans are written here by hand, made by the floor plan
generator's own code from its test fixture, or read from the parser's local cache when a
developer has one. The last tests hand a converted plan to PlanTo3D's furniture rules
(pure Python, vendored in services/planto3d) and check everything its builder reads.
"""

import copy
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import pytest

from app.modules.ai.floorplan.legacy_plan_json import to_legacy_plan_json
from app.modules.ai.floorplan.schemas.plan import FloorPlan
from app.modules.plan3d.convert import (
    INDOOR,
    PLANTO3D_TYPES,
    ConvertResult,
    check_plausible,
    planjson_to_planto3d,
    room_type,
    room_type_from_name,
)
from app.modules.plans.schemas import PlanJSON

BACKEND = Path(__file__).resolve().parents[2]
PLANTO3D = BACKEND.parent / "services" / "planto3d"
PARSER_CACHE = BACKEND / ".tmp" / "plan_cache"
GENERATOR_FIXTURE = BACKEND / "tests" / "floorplan" / "fixtures" / "sample_plan.json"

FT = 0.3048  # metres in a foot: the house below is drawn in whole feet


def m(feet: float) -> float:
    return round(feet * FT, 6)


def wall(wall_id: str, start: list[float], end: list[float], t: float, kind: str) -> dict:
    return {
        "id": wall_id,
        "start": [m(start[0]), m(start[1])],
        "end": [m(end[0]), m(end[1])],
        "thickness": m(t),
        "kind": kind,
    }


def opening(
    opening_id: str, wall_id: str, kind: str, offset: float, width: float, **more: Any
) -> dict:
    return {
        "id": opening_id,
        "wall_id": wall_id,
        "type": kind,
        "offset": m(offset),
        "width": m(width),
        "height": 2.1,
        **more,
    }


def room(room_id: str, name: str, x0: float, x1: float, y0: float, y1: float, **more: Any) -> dict:
    corners = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    return {"id": room_id, "name": name, "polygon": [[m(x), m(y)] for x, y in corners], **more}


def house() -> dict:
    """30 ft x 20 ft on wall centre lines, y down the page as the parser writes it.

        (0,0) ---- N: window ---------------- (30,0)
          |   BEDROOM      |      KITCHEN       |
          |               door                  |
        (0,20) -- S: door -------------------- (30,20)

    Outer walls 9 in (0.75 ft) thick, the partition at x = 15 is 6 in (0.5 ft).
    """
    level = {
        "index": 0,
        "name": "GROUND FLOOR PLAN",
        "walls": [
            wall("N", [0, 0], [30, 0], 0.75, "exterior"),
            wall("S", [0, 20], [30, 20], 0.75, "exterior"),
            wall("W", [0, 0], [0, 20], 0.75, "exterior"),
            wall("E", [30, 20], [30, 0], 0.75, "exterior"),
            wall("P", [15, 0], [15, 20], 0.5, "interior"),  # runs down the page
        ],
        "openings": [
            opening("D1", "S", "door", 5, 3),  # centre 5 ft from the west end
            opening("W1", "N", "window", 22.5, 4, sill=0.9),
            opening("D2", "P", "door", 5, 3),  # centre 5 ft below the north end
        ],
        "rooms": [
            room("R1", "BEDROOM 14'x19'", 0, 15, 0, 20, kind="indoor"),
            room("R2", "KITCHEN", 15, 30, 0, 20, kind="indoor"),
        ],
    }
    return {"version": 1, "units": "m", "scale_source": "dimension_label", "levels": [level]}


def convert(plan: dict, **options: Any) -> ConvertResult:
    PlanJSON.model_validate(plan)  # every input of these tests is a valid PlanJSON
    return planjson_to_planto3d(plan, **options)


def rects(items: list) -> list[list[float]]:
    return [[round(v, 3) for v in (i["rect"] if isinstance(i, dict) else i[:4])] for i in items]


# ---------------------------------------------------------------- the hand-made house
def test_house_becomes_exactly_these_rectangles() -> None:
    result = convert(house(), source_name="house.pdf")
    assert result.usable and result.reason == ""
    plan = result.plan
    assert plan is not None
    assert plan["units"] == "ft" and plan["version"] == 1 and plan["source"] == "house.pdf"
    assert plan["reader"] == "ai" and plan["scale_source"] == "labels"
    assert plan["floor_height"] == 10.0 and plan["slab"] == 0.5
    floor = plan["floors"][0]
    # the origin is the lower-left corner of the outer wall faces; rectangles overlap at corners
    assert floor["walls"] == [
        [0.0, 30.75, 20.0, 20.75, 0],  # N: at the top of the page, so at the largest y
        [0.0, 30.75, 0.0, 0.75, 0],  # S
        [0.0, 0.75, 0.0, 20.75, 0],  # W
        [30.0, 30.75, 0.0, 20.75, 0],  # E
        [15.125, 15.625, 0.0, 20.75, 0],  # the partition runs into both outer walls
    ]
    assert floor["size"] == [30.75, 20.75]
    assert floor["level"] == 0 and floor["name"] == "Ground Floor"
    assert floor["title"] == "GROUND FLOOR PLAN"
    assert floor["stairs"] == [] and floor["page"] == 1 and floor["origin_pt"] == [0.0, 0.0]


def test_openings_land_on_their_walls() -> None:
    floor = convert(house()).plan["floors"][0]  # type: ignore[index]
    assert floor["openings"] == [
        {"type": "door", "rect": [3.875, 6.875, 0.0, 0.75], "axis": "x"},
        {"type": "window", "rect": [20.875, 24.875, 20.0, 20.75], "axis": "x"},
        # 5 ft below the north end of the partition is 15 ft above the south wall's centre line
        {"type": "door", "rect": [15.125, 15.625, 13.875, 16.875], "axis": "y"},
    ]


def test_rooms_are_the_clear_floor_between_wall_faces() -> None:
    floor = convert(house()).plan["floors"][0]  # type: ignore[index]
    bedroom, kitchen = floor["rooms"]
    assert bedroom["rects"] == [[0.75, 15.125, 0.75, 20.0]]
    assert kitchen["rects"] == [[15.625, 30.0, 0.75, 20.0]]
    assert bedroom["type"] == "bedroom" and kitchen["type"] == "kitchen"
    assert bedroom["label"] == "BEDROOM 14'x19'" and bedroom["area"] == 276.7
    assert floor["labels"][0] == {"text": "BEDROOM 14'x19'", "at": [7.938, 10.375]}


def test_metres_become_feet() -> None:
    plan = house()
    plan["levels"][0]["walls"] = [
        {"id": "N", "start": [0, 0], "end": [3.048, 0], "thickness": 0.3048},
        {"id": "S", "start": [0, 3.048], "end": [3.048, 3.048], "thickness": 0.3048},
        {"id": "W", "start": [0, 0], "end": [0, 3.048], "thickness": 0.3048},
        {"id": "E", "start": [3.048, 0], "end": [3.048, 3.048], "thickness": 0.3048},
    ]
    plan["levels"][0]["openings"] = []
    plan["levels"][0]["rooms"] = []
    floor = convert(plan).plan["floors"][0]  # type: ignore[index]
    assert floor["size"] == [11.0, 11.0]  # 10 ft between centre lines + two half walls
    assert floor["walls"][0] == [0.0, 11.0, 10.0, 11.0, 0]


def test_y_axis_and_origin_do_not_depend_on_where_the_plan_was_drawn() -> None:
    shifted = house()
    for level in shifted["levels"]:
        for w in level["walls"]:
            w["start"] = [w["start"][0] + 12.5, w["start"][1] - 40.0]
            w["end"] = [w["end"][0] + 12.5, w["end"][1] - 40.0]
        for r in level["rooms"]:
            r["polygon"] = [[x + 12.5, y - 40.0] for x, y in r["polygon"]]
    assert convert(shifted).plan["floors"] == convert(house()).plan["floors"]  # type: ignore[index]

    # a plan whose y already grows up the page: the window wall is then the bottom one
    up = convert(house(), y_down=False).plan["floors"][0]  # type: ignore[index]
    assert up["openings"][1] == {"type": "window", "rect": [20.875, 24.875, 0.0, 0.75], "axis": "x"}


def test_an_offset_can_be_measured_to_the_near_edge_as_the_generator_does() -> None:
    floor = convert(house(), reader="generator").plan["floors"][0]  # type: ignore[index]
    # the same numbers now mean "the opening starts 5 ft along the wall"
    assert floor["openings"][0]["rect"] == [5.375, 8.375, 0.0, 0.75]
    assert floor["openings"][2]["rect"] == [15.125, 15.625, 12.375, 15.375]


def test_a_position_wins_over_the_offset() -> None:
    plan = house()
    plan["levels"][0]["openings"][0]["position"] = [m(10), m(20)]
    for reader in ("ai", "generator"):
        floor = planjson_to_planto3d(plan, reader=reader).plan["floors"][0]  # type: ignore[index]
        assert floor["openings"][0]["rect"] == [8.875, 11.875, 0.0, 0.75]


# ---------------------------------------------------------------- several levels
def test_levels_become_floors_in_order() -> None:
    plan = house()
    upper = copy.deepcopy(plan["levels"][0])
    upper.update(index=1, name="FIRST FLOOR PLAN", elevation=2.8)
    upper["walls"] = [w for w in upper["walls"] if w["id"] != "P"]
    upper["openings"] = [o for o in upper["openings"] if o["wall_id"] != "P"]
    upper["rooms"] = [room("R1", "FAMILY HALL", 0, 30, 0, 20)]
    for w in upper["walls"]:  # drawn somewhere else on the sheet
        w["start"] = [w["start"][0] + 20, w["start"][1]]
        w["end"] = [w["end"][0] + 20, w["end"][1]]
    upper["rooms"][0]["polygon"] = [[x + 20, y] for x, y in upper["rooms"][0]["polygon"]]
    plan["levels"].append(upper)
    plan["levels"].append({"index": 2, "name": "TERRACE", "walls": []})

    result = convert(plan)
    floors = result.plan["floors"]  # type: ignore[index]
    assert [(f["level"], f["name"]) for f in floors] == [(0, "Ground Floor"), (1, "First Floor")]
    assert floors[1]["size"] == [30.75, 20.75]
    assert floors[1]["walls"][0][:4] == [0, 30.75, 20, 20.75]  # from its own corner
    assert floors[1]["rooms"][0]["type"] == "living"
    assert any("Terrace: left out" in n for n in result.notes)
    assert any("no stair flights" in n for n in result.notes)
    assert result.plausible, result.problems


def test_a_stated_storey_height_is_used_and_kept_in_range() -> None:
    plan = house()
    plan["levels"][0].update(wall_height=3.3528, wall_height_source="stated")  # 11 ft
    assert convert(plan).plan["floor_height"] == 11.0  # type: ignore[index]
    plan["levels"][0]["wall_height"] = 6.0
    result = convert(plan)
    assert result.plan["floor_height"] == 14.0  # type: ignore[index]
    assert any("14.0 ft high" in n for n in result.notes)
    plan["levels"][0].update(wall_height=2.8, wall_height_source="default")
    assert convert(plan).plan["floor_height"] == 10.0  # type: ignore[index]


# ---------------------------------------------------------------- what cannot be kept
def test_a_slanted_wall_becomes_steps_or_is_left_out() -> None:
    plan = house()
    walls = plan["levels"][0]["walls"]
    walls.append(wall("X", [15, 20], [30, 5], 0.5, "interior"))  # 45 degrees, 21.2 ft
    plan["levels"][0]["openings"].append(opening("D3", "X", "door", 5, 3))

    result = convert(plan)
    floor = result.plan["floors"][0]  # type: ignore[index]
    steps = floor["walls"][5:]
    assert len(steps) == 22 and all(w[1] - w[0] < 1.3 and w[3] - w[2] < 1.3 for w in steps)
    assert steps[0][:4] == pytest.approx([15.125, 16.307, 0.125, 1.307], abs=0.002)
    assert any("wall X is slanted (21.2 ft) and is drawn as 22 short" in n for n in result.notes)
    assert any("door D3 was left out: its wall (X) is slanted" in n for n in result.notes)
    assert len(floor["openings"]) == 3

    skipped = convert(plan, diagonal="skip")
    assert len(skipped.plan["floors"][0]["walls"]) == 5  # type: ignore[index]
    assert any("wall X is slanted (21.2 ft) and was left out" in n for n in skipped.notes)


def test_a_nearly_straight_wall_is_straightened() -> None:
    plan = house()
    plan["levels"][0]["walls"][0]["end"] = [m(30), m(0.5)]  # N wall: 6 in off over 30 ft
    result = convert(plan)
    north = result.plan["floors"][0]["walls"][0]  # type: ignore[index]
    assert north[3] - north[2] == pytest.approx(0.75) and north[:2] == [0.0, 30.75]
    assert any("wall N was straightened" in n for n in result.notes)


def test_an_opening_wider_than_its_wall_is_narrowed() -> None:
    plan = house()
    plan["levels"][0]["openings"] = [opening("W9", "W", "window", 10, 40)]
    result = convert(plan)
    (window,) = result.plan["floors"][0]["openings"]  # type: ignore[index]
    # between the inner faces of the north and south walls: 20 ft - two half walls
    assert window == {"type": "window", "rect": [0.0, 0.75, 0.75, 20.0], "axis": "y"}
    assert any("window W9 is 40.0 ft wide" in n and "narrowed" in n for n in result.notes)


def test_openings_that_cannot_be_placed_are_dropped_with_a_note() -> None:
    plan = house()
    plan["levels"][0]["openings"] = [
        opening("A", "S", "door", 29.5, 3),  # overhangs the east end: moved back
        opening("B", "S", "door", 28, 3),  # overlaps A once A is moved
        opening("C", "nowhere", "door", 1, 3),
        opening("D", "N", "window", 5, 0),
    ]
    result = convert(plan)
    assert rects(result.plan["floors"][0]["openings"]) == [[27.0, 30.0, 0.0, 0.75]]  # type: ignore[index]
    text = " | ".join(result.notes)
    assert "door A ran past the end of its wall and was moved onto it" in text
    assert "door B was left out: it overlaps another opening" in text
    assert "door C was left out: its wall (nowhere) is not in the plan" in text
    assert "window D was left out: it has no position or no width" in text


def test_a_wall_is_lengthened_to_hold_openings_drawn_past_its_end() -> None:
    """A real parser result: the south wall stopped a quarter of the way along, while the
    openings on it kept their offsets (and their `position` was pinned to the wall's end)."""
    plan = house()
    level = plan["levels"][0]
    level["walls"][1] = wall("S", [0, 20], [8, 20], 0.75, "exterior")
    level["openings"] = [
        opening("D1", "S", "door", 5, 3),
        opening("D2", "S", "door", 14, 3, position=[m(8), m(20)]),
        opening("W2", "S", "window", 26, 4, position=[m(8), m(20)]),
    ]
    result = convert(plan)
    floor = result.plan["floors"][0]  # type: ignore[index]
    # the last opening ends at 28 ft; the east wall is 2 ft further, so the wall runs to it
    assert floor["walls"][1] == [0.0, 30.75, 0.0, 0.75, 0]
    assert rects(floor["openings"]) == [
        [3.875, 6.875, 0.0, 0.75],
        [12.875, 15.875, 0.0, 0.75],
        [24.375, 28.375, 0.0, 0.75],
    ]
    assert any("wall S is drawn 8.0 ft long" in n and "30.0 ft" in n for n in result.notes)
    assert result.plausible, result.problems


def test_an_l_shaped_and_a_slanted_room() -> None:
    plan = house()
    corners = [[0, 0], [15, 0], [15, 10], [8, 10], [8, 20], [0, 20]]
    plan["levels"][0]["rooms"] = [
        {"id": "L", "name": "LIVING", "polygon": [[m(x), m(y)] for x, y in corners]},
        {"id": "T", "name": "STORE", "polygon": [[m(16), m(1)], [m(29), m(1)], [m(16), m(14)]]},
    ]
    result = convert(plan)
    living, store = result.plan["floors"][0]["rooms"]  # type: ignore[index]
    assert living["rects"] == [[0.75, 8.375, 0.75, 10.375], [0.75, 15.125, 10.375, 20.0]]
    assert store["area"] == pytest.approx(84.5, abs=5)  # a 13 ft right triangle
    assert any("room STORE has slanted edges" in n for n in result.notes)


def test_walls_beside_outdoor_rooms_only_are_low() -> None:
    plan = house()
    level = plan["levels"][0]
    level["walls"] += [
        wall("G1", [30, 20], [40, 20], 0.5, "exterior"),
        wall("G2", [40, 20], [40, 0], 0.5, "exterior"),
        wall("G3", [30, 0], [40, 0], 0.5, "exterior"),
    ]
    level["rooms"].append(room("R3", "LAWN", 30, 40, 0, 20, kind="outdoor"))
    result = convert(plan)
    floor = result.plan["floors"][0]  # type: ignore[index]
    assert [w[4] for w in floor["walls"]] == [0, 0, 0, 0, 0, 1, 1, 1]  # E keeps its height
    assert floor["rooms"][2]["type"] == "garden"
    assert any("3 wall(s) beside outdoor areas only are built low" in n for n in result.notes)


# ---------------------------------------------------------------- room types
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("MASTER BED ROOM 16'4\"X11'4\"", "bedroom"),
        ("DRESS/TOI. 7'X11'6", "toilet"),
        ("DRG./DIN. 17'9 X 21'", "dining"),
        ("KIT. 12'6X10'", "kitchen"),
        ("ENT.LOBBY 5'X10'4", "passage"),
        ("SITOUT 26' X 8'", "balcony"),
        ("LAWN 4' WD.", "garden"),
        ("OPEN 3' WD.", "open"),
        ("STAIRCASE", "stair"),
        ("FAMILY HALL 620X400", "living"),
        ("W.C", "toilet"),
        ("ROOM", None),
        ("", None),
    ],
)
def test_room_names_are_typed_as_planto3d_types_them(name: str, expected: str | None) -> None:
    assert room_type_from_name(name) == expected


def test_room_type_prefers_the_most_reliable_source() -> None:
    assert room_type({"name": "SWIMMING POOL", "tag": "pool"}) == "yard"
    assert room_type({"name": "BED ROOM", "tag": "maid_room"}) == "bedroom"
    assert room_type({"name": "LIVING", "type": "puja"}) == "puja"
    assert room_type({"name": "MAID ROOM 300X250", "boq_type": "BED"}) == "bedroom"
    assert room_type({"name": "AREA 1", "kind": "outdoor"}) == "yard"
    assert room_type({"name": "AREA 2", "kind": "void"}) == "open"
    assert room_type({"name": None}) == "room"
    assert {room_type({"tag": t}) for t in ("bath", "courtyard", "shaft")} <= set(PLANTO3D_TYPES)


# ---------------------------------------------------------------- inputs that cannot be used
@pytest.mark.parametrize(
    ("plan", "reason"),
    [
        ({}, "no levels"),
        ({"levels": []}, "no levels"),
        ({"levels": [{"walls": [], "rooms": [], "openings": []}]}, "no walls"),
        ({"units": "furlong", "levels": [{"walls": []}]}, "unknown unit"),
    ],
)
def test_a_plan_with_nothing_to_build_is_unusable(plan: dict, reason: str) -> None:
    result = planjson_to_planto3d(plan)
    assert not result.usable and not result.plausible and result.plan is None
    assert reason in result.reason


def test_schema_valid_nonsense_never_raises() -> None:
    nan, inf = float("nan"), float("inf")
    level = {
        "walls": [
            {"id": "a", "start": [0, 0], "end": [0, 0]},  # no length
            {"id": "b", "start": [nan, 0], "end": [1, 1]},
            {"id": "c", "start": [0, 0], "end": [inf, 0]},
            {"id": "d", "start": [0, 0], "end": [4, 0], "thickness": -1},
            {"id": "d", "start": [0, 0], "end": [0, 4], "thickness": 99},  # the id again
        ],
        "openings": [
            {"id": "o1", "wall_id": "d", "type": "door", "offset": nan, "width": 1, "height": 2},
            {"id": "o2", "wall_id": "d", "type": "door", "offset": 1, "width": inf, "height": 2},
            {"id": "o3", "wall_id": "a", "type": "window", "offset": -5, "width": 1, "height": 1},
        ],
        "rooms": [
            {"id": "r1", "polygon": []},
            {"id": "r2", "polygon": [[0, 0], [1, 1]]},
            {"id": "r3", "name": None, "polygon": [[0, 0], [nan, 1], [1, 1], [1, 0]]},
            {"id": "r4", "polygon": [[0, 0], [0, 0], [0, 0]]},
        ],
        "columns": [{"id": "c1", "position": [nan, 0]}, {"id": "c2", "position": [2, 2]}],
    }
    plan = {"levels": [level, {}, {"walls": [{"id": "x", "start": [0, 0], "end": [1, 0]}]}]}
    PlanJSON.model_validate(plan)
    result = planjson_to_planto3d(plan)
    assert result.usable and not result.plausible
    json.dumps(result.plan, allow_nan=False)  # nothing unreal reaches PlanTo3D
    for not_a_plan in (None, [], "plan", 3, {"levels": "x"}, {"levels": [None, 3]}):
        assert not planjson_to_planto3d(not_a_plan).usable  # type: ignore[arg-type]


# ---------------------------------------------------------------- plausibility
def test_the_house_is_plausible() -> None:
    result = convert(house())
    assert result.plausible and result.problems == [] and check_plausible(result.plan) == []  # type: ignore[arg-type]


def test_what_looks_implausible() -> None:
    def problems(change: Any) -> str:
        plan = house()
        change(plan["levels"][0])
        return " | ".join(convert(plan).problems)

    assert "not closed" in problems(lambda lv: lv["walls"].pop(3))  # no east wall
    assert "only 3 wall(s)" in problems(lambda lv: lv.update(walls=lv["walls"][:3], openings=[]))
    assert "no door" in problems(lambda lv: lv.update(openings=lv["openings"][1:2]))
    assert "no indoor room" in problems(lambda lv: lv.update(rooms=[]))
    far = room("R9", "BEDROOM", 100, 115, 0, 20)
    assert "lies outside the walls" in problems(lambda lv: lv["rooms"].append(far))

    millimetres = house()  # a plan in millimetres that says metres
    for w in millimetres["levels"][0]["walls"]:
        w["start"] = [v * 1000 for v in w["start"]]
        w["end"] = [v * 1000 for v in w["end"]]
    assert "expected between 8 and 300 ft" in " | ".join(convert(millimetres).problems)
    assert check_plausible({}) == ["The plan has no floors."]


def test_planto3d_own_detector_output_passes_the_same_check() -> None:
    """The sample plan as PlanTo3D's detector reads it (walls of its bedroom wing only)."""
    floor = {
        "name": "Ground Floor",
        "walls": [
            [0.0, 12.5, 0.0, 0.75, 0], [0.0, 0.75, 0.0, 12.75, 0], [0.0, 12.5, 12.0, 12.75, 0],
            [11.75, 12.5, 0.0, 12.75, 0],
        ],
        "openings": [{"type": "door", "rect": [4.0, 7.0, 0.0, 0.75], "axis": "x"}],
        "rooms": [{"type": "bedroom", "label": "BEDROOM", "rects": [[1.0, 11.75, 1.0, 12.0]]}],
        "stairs": [],
    }  # fmt: skip
    assert check_plausible({"floors": [floor]}) == []
    floor["openings"] = []
    floor["walls"][0] = [0.0, 4.0, 0.0, 0.75, 0]  # the door became a hole in the wall
    assert any("not closed" in p for p in check_plausible({"floors": [floor]}))


# ---------------------------------------------------------------- the registration hook
def test_registration_is_merged_as_given() -> None:
    registration = {
        "plan": {"scale_pt_per_ft": 8.5},
        "floors": [{"page": 2, "origin_pt": [100.0, 700.0]}],
    }
    plan = convert(house(), registration=registration).plan
    assert plan is not None and plan["scale_pt_per_ft"] == 8.5
    assert plan["floors"][0]["page"] == 2 and plan["floors"][0]["origin_pt"] == [100.0, 700.0]
    assert convert(house()).plan["scale_pt_per_ft"] == 12.0  # type: ignore[index]


# ---------------------------------------------------------------- real plans
def assert_buildable(plan: dict) -> None:
    """Everything PlanTo3D reads without a default: web/edit.js, furnish.py, blender/gen.py."""
    json.dumps(plan, allow_nan=False)
    assert plan["floors"] and plan["scale_pt_per_ft"] > 0 and 8 <= plan["floor_height"] <= 14
    for floor in plan["floors"]:
        assert floor["walls"], "gen.py takes the bounding box of the walls"
        assert len(floor["size"]) == 2 and len(floor["origin_pt"]) == 2 and floor["name"]
        assert isinstance(floor["stairs"], list), "gen.py reads f['stairs'] without a default"
        for w in floor["walls"]:
            assert len(w) == 5 and w[4] in (0, 1)
            assert w[0] < w[1] and w[2] < w[3] and min(w[:4]) >= 0
            assert w[1] <= floor["size"][0] + 0.01 and w[3] <= floor["size"][1] + 0.01
        for o in floor["openings"]:
            assert o["type"] in ("door", "window", "opening") and o["axis"] in ("x", "y")
            r = o["rect"]
            assert r[0] < r[1] and r[2] < r[3]
            along = (r[1] - r[0]) if o["axis"] == "x" else (r[3] - r[2])
            assert along >= 1.0, "an opening runs along its wall"
            assert any(  # it lies across a wall, so cutting it leaves a doorway, not a notch
                w[0] - 0.01 <= r[0] and r[1] <= w[1] + 0.01 and w[2] - 0.01 <= r[2]
                and r[3] <= w[3] + 0.01
                for w in floor["walls"]
            )  # fmt: skip
        for z in floor["rooms"]:
            assert z["type"] in PLANTO3D_TYPES and isinstance(z["label"], str)
            assert z["rects"], "gen.py takes the largest rectangle of every room"
            assert all(len(r) == 4 and r[0] < r[1] and r[2] < r[3] for r in z["rects"])
            assert z["area"] == pytest.approx(
                sum((r[1] - r[0]) * (r[3] - r[2]) for r in z["rects"]), abs=0.06
            )
            for a in z["rects"]:  # the clear floor: no room rectangle runs under a wall
                assert not any(
                    a[0] < w[1] - 0.02 and w[0] < a[1] - 0.02 and a[2] < w[3] - 0.02
                    and w[2] < a[3] - 0.02
                    for w in floor["walls"]
                )  # fmt: skip


def furniture_clashes(plan: dict) -> list[str]:
    """PlanTo3D's own furniture rules and clash check on every floor."""
    spec = importlib.util.spec_from_file_location("planto3d_furnish", PLANTO3D / "furnish.py")
    assert spec and spec.loader
    furnish = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(furnish)
    clashes: list[str] = []
    placed = 0
    for floor in copy.deepcopy(plan)["floors"]:
        items = furnish.furnish_floor(floor)
        placed += len(items)
        clashes += furnish.clashes(items, floor)
    assert placed > 0, "no furniture was placed at all"
    return clashes


needs_planto3d = pytest.mark.skipif(
    not (PLANTO3D / "furnish.py").is_file(), reason="services/planto3d is not checked out"
)


def test_the_house_satisfies_what_planto3d_reads() -> None:
    plan = convert(house()).plan
    assert plan is not None
    assert_buildable(plan)


@needs_planto3d
def test_the_house_is_furnished_by_planto3d_without_clashes() -> None:
    plan = convert(house()).plan
    assert plan is not None and furniture_clashes(plan) == []


def generator_plan() -> tuple[FloorPlan, dict]:
    floor_plan = FloorPlan.model_validate(json.loads(GENERATOR_FIXTURE.read_text("utf-8")))
    return floor_plan, to_legacy_plan_json(floor_plan)


def test_a_generator_plan_converts_and_is_plausible() -> None:
    floor_plan, stored = generator_plan()
    result = convert(stored, source_name="generated", reader="generator")
    assert result.plausible, result.problems
    plan = result.plan
    assert plan is not None and plan["reader"] == "generator"
    assert_buildable(plan)
    floor = plan["floors"][0]
    # nothing the generator drew is lost: every room, door and window arrives
    assert len(floor["rooms"]) == len(floor_plan.rooms)
    assert [o["type"] for o in floor["openings"]].count("door") == len(floor_plan.doors)
    assert [o["type"] for o in floor["openings"]].count("window") == len(floor_plan.windows)
    assert not any("left out" in n or "narrowed" in n or "moved" in n for n in result.notes)
    # the walls' bounding box is the built outline plus half an outer wall each side
    outer = 0.23 / FT
    xs = [w[k] * 100 * FT for w in floor["walls"] for k in (0, 1)]
    built_width = max(xs) - min(xs) - outer * 100 * FT
    enclosed = [r for r in floor_plan.rooms if not r.is_open]
    assert built_width == pytest.approx(
        max(r.x2 for r in enclosed) - min(r.x for r in enclosed), abs=1.0
    )
    # a door keeps its width and the middle the generator gave it
    door = floor_plan.doors[0]
    converted = floor["openings"][0]
    r = converted["rect"]
    width = (r[1] - r[0]) if converted["axis"] == "x" else (r[3] - r[2])
    assert width == pytest.approx(door.width / 100 / FT, abs=0.01)


@needs_planto3d
def test_a_generator_plan_is_furnished_without_clashes() -> None:
    _, stored = generator_plan()
    plan = convert(stored, reader="generator").plan
    assert plan is not None and furniture_clashes(plan) == []


def cached_parser_plans() -> list[Path]:
    """The newest parser result for each PDF (the cache keeps older parser versions too)."""
    newest: dict[str, Path] = {}
    for path in sorted(PARSER_CACHE.glob("*.parser-*.json")) if PARSER_CACHE.is_dir() else []:
        newest[path.name.split(".")[0]] = path  # sorted: a later version replaces an earlier
    return list(newest.values())


@pytest.mark.skipif(not cached_parser_plans(), reason="no parser cache on this machine")
def test_real_parser_output_converts_and_is_plausible() -> None:
    """The parser's cached results for the owner's sample PDFs (local, never committed)."""
    checked = 0
    for path in cached_parser_plans():
        stored = json.loads(path.read_text("utf-8"))
        if not isinstance(stored, dict) or stored.get("schema_version") != "2.0":
            continue
        PlanJSON.model_validate(stored)
        result = planjson_to_planto3d(stored, source_name=path.name)
        assert result.usable, (path.name, result.reason)
        assert result.plan is not None
        assert_buildable(result.plan)
        assert len(result.plan["floors"]) == len(stored["levels"])
        assert result.plausible, (path.name, result.problems)
        for floor, level in zip(result.plan["floors"], stored["levels"], strict=True):
            assert len(floor["rooms"]) >= 0.9 * len(level["rooms"]), path.name
            assert len(floor["openings"]) >= 0.8 * len(level["openings"]), path.name
            assert not math.isnan(floor["size"][0])
        checked += 1
    assert checked, "the cache holds no schema 2.0 plan"


def test_a_parser_style_plan_converts() -> None:
    """How the parser writes a plan: rooms on the inner wall faces, `position` on every
    opening, columns, `kind` and `boq_type` on rooms, long walls that others run into."""
    level = {
        "index": 0,
        "name": "Floor Plan",
        "elevation": 0.0,
        "wall_height": 2.8,
        "wall_height_source": "default",
        "walls": [
            {"id": "L0-W01", "start": [0.0, 0.0], "end": [8.0, 0.0], "thickness": 0.23,
             "kind": "exterior", "is_exterior": True, "inferred": False},
            {"id": "L0-W02", "start": [0.0, 0.0], "end": [0.0, 6.0], "thickness": 0.23,
             "kind": "exterior", "is_exterior": True, "inferred": False},
            {"id": "L0-W03", "start": [8.0, 0.0], "end": [8.0, 6.0], "thickness": 0.23,
             "kind": "exterior", "is_exterior": True, "inferred": False},
            {"id": "L0-W04", "start": [0.0, 6.0], "end": [8.0, 6.0], "thickness": 0.23,
             "kind": "exterior", "is_exterior": True, "inferred": False},
            {"id": "L0-W05", "start": [4.5, 0.0], "end": [4.5, 6.0], "thickness": 0.115,
             "kind": "interior", "is_exterior": False, "inferred": False},
            {"id": "L0-W06", "start": [4.5, 3.5], "end": [8.0, 3.5], "thickness": 0.115,
             "kind": "interior", "is_exterior": False, "inferred": True},
        ],
        "openings": [
            {"id": "L0-O01", "wall_id": "L0-W04", "type": "door", "offset": 2.0, "width": 1.0,
             "height": 2.1, "sill": 0.0, "sill_height": 0.0, "position": [2.0, 6.0]},
            {"id": "L0-O02", "wall_id": "L0-W05", "type": "door", "offset": 1.5, "width": 0.9,
             "height": 2.1, "sill": 0.0, "sill_height": 0.0, "position": [4.5, 1.5]},
            {"id": "L0-O03", "wall_id": "L0-W05", "type": "door", "offset": 4.8, "width": 0.75,
             "height": 2.1, "sill": 0.0, "sill_height": 0.0, "position": [4.5, 4.8]},
            {"id": "L0-O04", "wall_id": "L0-W01", "type": "window", "offset": 2.2, "width": 1.5,
             "height": 1.2, "sill": 0.9, "sill_height": 0.9, "position": [2.2, 0.0]},
            {"id": "L0-O05", "wall_id": "L0-W03", "type": "window", "offset": 1.7, "width": 1.2,
             "height": 1.2, "sill": 0.9, "sill_height": 0.9, "position": [8.0, 1.7]},
        ],
        "rooms": [
            {"id": "L0-R01", "name": "DRG./DIN. 14'X19'", "kind": "indoor", "boq_type": "LIVING",
             "polygon": [[0.12, 0.12], [4.44, 0.12], [4.44, 5.88], [0.12, 5.88]]},
            {"id": "L0-R02", "name": "BED ROOM 350X330", "kind": "indoor", "boq_type": "BED",
             "polygon": [[4.56, 0.12], [7.88, 0.12], [7.88, 3.44], [4.56, 3.44]]},
            {"id": "L0-R03", "name": "TOI. 11'X7'6", "kind": "indoor", "boq_type": "BATH",
             "polygon": [[4.56, 3.56], [7.88, 3.56], [7.88, 5.88], [4.56, 5.88]]},
        ],
        "columns": [{"id": "L0-C01", "position": [0.0, 0.0], "width": 0.23, "depth": 0.23}],
    }  # fmt: skip
    plan = {
        "schema_version": "2.0", "version": 1, "units": "m", "building_type": "villa",
        "scale_source": "dimension_label", "levels": [level], "confidence": {"overall": 0.8},
    }  # fmt: skip
    result = convert(plan, source_name="scan.pdf")
    assert result.plausible, result.problems
    assert result.plan is not None
    assert_buildable(result.plan)
    floor = result.plan["floors"][0]
    assert floor["name"] == "Ground Floor"  # "Floor Plan" names nothing
    assert floor["size"] == [27.0, 20.44]
    assert len(floor["walls"]) == 6  # the corner column is inside the walls already
    assert [z["type"] for z in floor["rooms"]] == ["dining", "bedroom", "toilet"]
    assert [o["type"] for o in floor["openings"]] == ["door", "door", "door", "window", "window"]
    assert result.notes == []
    assert INDOOR >= {z["type"] for z in floor["rooms"]}
    if (PLANTO3D / "furnish.py").is_file():
        assert furniture_clashes(result.plan) == []
