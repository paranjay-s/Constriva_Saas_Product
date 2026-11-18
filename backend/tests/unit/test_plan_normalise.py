"""The deterministic PlanJSON normaliser and the shared room-kind rules."""

import copy
import json
from pathlib import Path

import pytest

from app.modules.parsing.normalise import (
    clean_polygon,
    normalise_building_type,
    normalise_opening_type,
    normalise_plan,
    signed_area,
    stated_area_m2,
    to_metres,
    upgrade_plan,
)
from app.modules.plans.room_kind import is_open_void_label, parser_room_kind
from app.modules.plans.room_types import (
    BOQ_TYPES,
    boq_type_from_name,
    is_open_plan_kitchen,
    resolve_boq_type,
    stored_or_derived_boq_type,
)
from app.modules.plans.schemas import SCHEMA_VERSION, UNSTATED_WALL_HEIGHT_M, PlanJSON
from app.modules.sheets.llm_mapper import _classify_room_kind

EXTRACTED_PLAN = Path(__file__).resolve().parents[2] / "extracted_plan.json"


def raw_plan() -> dict:
    """A small plan as a model might return it: feet, unsorted, mixed-quality fields."""
    return {
        "units": "ft",
        "building_type": "Independent house",
        "scale_source": "dimension_label",
        "levels": [
            {
                "name": "Ground Floor Plan",
                "rooms": [
                    {
                        "id": "kitchen",
                        "name": "Open Kitchen 10' X 10'",
                        "kind": "indoor",
                        "polygon": [[10, 0], [20, 0], [20, 10], [10, 10], [10, 0]],
                    },
                    {
                        "id": "bed",
                        "name": "BEDROOM 10' X 10'",
                        "kind": "indoor",
                        # clockwise, with a repeated point
                        "polygon": [[0, 0], [0, 10], [0, 10], [10, 10], [10, 0]],
                    },
                    {
                        "id": "shaft",
                        "name": "OPEN 4'6\"X10'",
                        "kind": "indoor",
                        "polygon": [[20, 0], [24.5, 0], [24.5, 10], [20, 10]],
                    },
                ],
                "walls": [
                    {
                        "id": "s",
                        "start": [0, 10],
                        "end": [24.5, 10],
                        "thickness": 0.75,
                        "kind": "exterior",
                    },
                    {
                        "id": "n",
                        "start": [0, 0],
                        "end": [24.5, 0],
                        "thickness": 0.75,
                        "kind": "exterior",
                    },
                    {"id": "w", "start": [0, 0], "end": [0, 10], "thickness": 0.75},
                    {"id": "e", "start": [24.5, 0], "end": [24.5, 10], "thickness": 0.75},
                    {"id": "mid", "start": [10, 0], "end": [10, 10], "thickness": 0.4},
                ],
                "openings": [
                    {
                        "id": "d",
                        "wall_id": "mid",
                        "type": "Main Door",
                        "offset": 5,
                        "width": 3,
                        "height": 7,
                    },
                    {
                        "id": "x",
                        "wall_id": "n",
                        "type": "WINDOW",
                        "offset": 5,
                        "width": 4,
                        "height": 4,
                        "sill": 3,
                    },
                ],
                "columns": [{"id": "c", "position": [0, 0]}],
            }
        ],
    }


# ------------------------------------------------------------------------ room kind


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Open Kitchen", False),
        ("OPEN PLAN LIVING", False),
        ("Open Terrace", False),
        ("OPEN", True),
        ("OPEN 4'6\"X10'4\"", True),
        ("OPEN 3' WD.", True),
        ("Open to Sky", True),
        ("OPEN SHAFT", True),
        ("", False),
        (None, False),
    ],
)
def test_open_only_marks_real_voids(name, expected):
    assert is_open_void_label(name) is expected


def test_open_kitchen_is_no_longer_a_void_in_the_calculator():
    assert _classify_room_kind({"name": "Open Kitchen"}) == "indoor"
    assert _classify_room_kind({"name": "OPEN TO SKY"}) == "void"
    assert _classify_room_kind({"name": "Open Shaft"}) == "void"
    assert _classify_room_kind({"name": "OPEN 4'8\" X 9'"}) == "void"
    assert _classify_room_kind({"name": "Duct"}) == "void"
    # an explicit kind still wins in the calculator
    assert _classify_room_kind({"name": "Open Kitchen", "kind": "void"}) == "void"


@pytest.mark.parametrize(
    ("name", "reported", "expected"),
    [
        ("Open Kitchen", "indoor", "indoor"),
        ("Open Kitchen", None, "indoor"),
        ("LAWN 10'8\" X 8'", "indoor", "outdoor"),
        ("COURTYARD", "indoor", "outdoor"),
        ("VERANDAH", "indoor", "semi_open"),
        ("PARKING 18'X16'", "outdoor", "semi_open"),
        ("OPEN 4'6\"X10'", "indoor", "void"),
        ("SHAFT", "indoor", "void"),
        ("BEDROOM", "semi_open", "semi_open"),
        ("BEDROOM", "nonsense", "indoor"),
    ],
)
def test_parser_kind_rules(name, reported, expected):
    assert parser_room_kind(name, reported) == expected


# ------------------------------------------------------------------- room boq_type


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # rule 1 wins over everything below it
        ("Master Bath", "BATH"),
        ("GUEST TOILET", "BATH"),
        ("TOI. 9' X 5'", "BATH"),
        ("DRESS/TOI. 7'X11'6\"", "BATH"),
        ("W.C.", "BATH"),
        ("Washroom", "BATH"),  # before LAUNDRY's "wash"
        ("Powder Room", "BATH"),
        ("Ensuite", "BATH"),
        ("Kitchen", "KITCHEN"),
        ("Open Kitchen", "KITCHEN"),
        ("Pantry", "KITCHEN"),
        ("Laundry", "LAUNDRY"),
        ("Utility", "LAUNDRY"),
        ("WASH 7' X 4'", "LAUNDRY"),
        ("Hallway", "CIRC"),  # before LIVING's "hall"
        ("Corridor", "CIRC"),
        ("PASSAGE 3'4\" WD.", "CIRC"),
        ("ENT.LOBBY 5'X10'4", "CIRC"),
        ("Staircase", "CIRC"),
        ("Living Room", "LIVING"),
        ("Majlis", "LIVING"),
        ("FAMILY HALL 620X400", "LIVING"),
        ("Drawing Room", "LIVING"),
        ("Dining", "DINING"),
        ("STORE 4'8\" X 4'", "STORE"),
        ("Dressing", "STORE"),
        ("Walk-in Closet", "STORE"),
        ("BED ROOM 500X400", "BED"),
        ("Master Suite", "BED"),
        ("MAID ROOM 250", "BED"),
        ("Guest Room", "BED"),
        ("Study", "STUDY"),
        ("Home Office", "STUDY"),
        ("Hall", "LIVING"),  # rule 10
        ("Room 1", "OTHER"),
        ("KIT. 12'6X10'", "OTHER"),  # abbreviations are left to the model
        ("DRG./DIN. 17'9 X 21'", "OTHER"),
        ("", "OTHER"),
        (None, "OTHER"),
    ],
)
def test_boq_type_keyword_rules(name, expected):
    assert boq_type_from_name(name) == expected
    assert expected in BOQ_TYPES


@pytest.mark.parametrize(
    ("name", "open_plan"),
    [
        ("Living / Dining / Kitchen", True),
        ("Kitchen + Family", True),
        ("Lounge with Pantry", True),
        ("Kitchen Hall", True),
        ("Open Kitchen", False),
        ("Kitchen", False),
        ("Living Room", False),
        ("Dining", False),
    ],
)
def test_open_plan_kitchen_is_a_living_room(name, open_plan):
    assert is_open_plan_kitchen(name) is open_plan
    if open_plan:
        assert boq_type_from_name(name) == "LIVING"


def test_rules_win_and_the_model_fills_in_only_for_other():
    assert resolve_boq_type("Master Bedroom", "KITCHEN") == "BED"  # rule beats the model
    assert resolve_boq_type("KIT. 12'6X10'", "KITCHEN") == "KITCHEN"  # abbreviated label
    assert resolve_boq_type("\u0645\u0637\u0628\u062e", "kitchen") == "KITCHEN"  # Arabic label
    assert resolve_boq_type("Room 1", "PLAYROOM") == "OTHER"  # not a valid code
    assert resolve_boq_type("Room 1", None) == "OTHER"


def test_a_stored_boq_type_is_kept_and_a_missing_one_is_derived():
    assert stored_or_derived_boq_type("Room 1", "BED") == "BED"
    assert stored_or_derived_boq_type("Master Bedroom", None) == "BED"
    assert stored_or_derived_boq_type("Master Bedroom", "not-a-type") == "BED"
    assert stored_or_derived_boq_type("Room 1", None) == "OTHER"


def test_normaliser_types_indoor_rooms_only():
    raw = raw_plan()
    raw["levels"][0]["rooms"][0]["boq_type"] = "BED"  # the model's (wrong) answer for a kitchen
    raw["levels"][0]["rooms"].append(
        {
            "id": "x",
            "name": "KIT. 10' X 10'",
            "kind": "indoor",
            "boq_type": "KITCHEN",
            "polygon": [[0, 5], [5, 5], [5, 10], [0, 10]],
        }
    )
    rooms = {r["name"]: r for r in normalise_plan(raw)["levels"][0]["rooms"]}
    assert rooms["Open Kitchen 10' X 10'"]["boq_type"] == "KITCHEN"  # keyword rule wins
    assert rooms["BEDROOM 10' X 10'"]["boq_type"] == "BED"
    assert rooms["KIT. 10' X 10'"]["boq_type"] == "KITCHEN"  # rules gave OTHER: model used
    assert rooms["OPEN 4'6\"X10'"]["kind"] == "void"
    assert rooms["OPEN 4'6\"X10'"]["boq_type"] is None  # not an indoor room


def test_room_type_key_of_the_3d_adapter_is_never_read_written_or_changed():
    # a fresh parse does not create it, whatever the model sends
    raw = raw_plan()
    raw["levels"][0]["rooms"][0]["type"] = "bedroom"  # wrong on purpose: must not be read
    parsed = normalise_plan(raw)
    assert all("type" not in r for r in parsed["levels"][0]["rooms"])
    assert parsed["levels"][0]["rooms"][1]["boq_type"] == "KITCHEN"

    # a stored plan keeps it exactly as it was, next to the new boq_type
    stored = {
        "levels": [
            {
                "furniture": [{"type": "sofa", "position": [1, 1]}],
                "rooms": [
                    {
                        "id": "r",
                        "name": "Master Bedroom",
                        "kind": "indoor",
                        "type": "bedroom",
                        "dimensions": "12' X 14'",
                        "polygon": [[0, 0], [4, 0], [4, 5], [0, 5]],
                    },
                    {
                        "id": "k",
                        "name": "Kitchen",
                        "kind": "indoor",
                        "type": "toilet",
                        "polygon": [[4, 0], [8, 0], [8, 5], [4, 5]],
                    },
                ],
                "walls": [
                    {"id": "w", "start": [0, 0], "end": [8, 0], "height": 3.1, "type": "exterior"}
                ],
            }
        ]
    }
    upgraded = upgrade_plan(stored)
    bed, kitchen = upgraded["levels"][0]["rooms"]
    assert (bed["type"], bed["dimensions"], bed["boq_type"]) == ("bedroom", "12' X 14'", "BED")
    assert (kitchen["type"], kitchen["boq_type"]) == ("toilet", "KITCHEN")  # type ignored
    assert upgraded["levels"][0]["walls"][0]["height"] == 3.1
    assert upgraded["levels"][0]["furniture"] == [{"type": "sofa", "position": [1, 1]}]
    assert (
        PlanJSON.model_validate(upgraded).model_dump()["levels"][0]["rooms"][0]["type"] == "bedroom"
    )


# -------------------------------------------------------------------------- helpers


def test_to_metres():
    assert to_metres(10, 0.3048) == 3.048
    assert to_metres("12'6\"", 1.0) == 3.81
    assert to_metres("9'", 1.0) == 2.743
    assert to_metres("3.5", 1.0) == 3.5
    assert to_metres("abc") is None
    assert to_metres(float("nan")) is None
    assert to_metres(True) is None
    assert to_metres(None) is None


def test_clean_polygon_canonical_form():
    square = clean_polygon([[2, 0], [2, 2], [0, 2], [0, 0], [2, 0], [2, 0]])
    assert square == [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]]
    assert signed_area(square) > 0  # counter-clockwise
    # the same room started at another corner and wound the other way is the same polygon
    assert clean_polygon([[0, 2], [0, 0], [2, 0], [2, 2]]) == square
    assert clean_polygon([[0, 0], [1.23456, 0], [1.23456, 1], [0, 1]])[1] == [1.235, 0.0]


@pytest.mark.parametrize(
    "points",
    [
        [[0, 0], [1, 1]],  # two points
        [[0, 0], [1, 1], [2, 2]],  # no area
        [[0, 0], [0, 0], [0, 0], [0, 0]],  # one point repeated
        "not a polygon",
        [[0, 0], ["a", 1], [1, "b"]],
    ],
)
def test_clean_polygon_rejects_unusable_outlines(points):
    assert clean_polygon(points) is None


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("BEDROOM 12'6\" X 14'", 16.258),
        ("BEDROOM 15'9X11'6", 16.827),
        ("BED ROOM 500X400", 20.0),
        ("LIVING 3.5 x 4.2", 14.7),
        ("HALL 3500 x 4200", 14.7),
        ("HALL 120 SQ.FT", 11.148),
        ("STORE 6.5 sqm", 6.5),
        ("PASSAGE 3'4\" WD.", None),
        ("KITCHEN", None),
        (None, None),
    ],
)
def test_stated_area(label, expected):
    assert stated_area_m2(label) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("door", "door"),
        ("Main Door", "door"),
        ("SLIDING DOOR", "door"),
        ("gate", "door"),
        ("window", "window"),
        ("WINDOW", "window"),
        ("Ventilator", "window"),
        ("glazing", "window"),
        ("D", "door"),
        ("W", "window"),
    ],
)
def test_opening_type_is_always_door_or_window(raw, expected):
    assert normalise_opening_type(raw) == expected


def test_opening_type_without_a_label_uses_its_shape():
    assert normalise_opening_type(None, sill=0.9, height=1.2) == "window"
    assert normalise_opening_type("", sill=0.0, height=2.1) == "door"


def test_building_type():
    assert normalise_building_type("Apartment block") == "apartment"
    assert normalise_building_type("2BHK flat") == "apartment"
    assert normalise_building_type("villa") == "villa"
    assert normalise_building_type("Duplex house") == "villa"
    assert normalise_building_type(None) == "other"
    assert normalise_building_type("warehouse") == "other"


# ------------------------------------------------------------------------ normaliser


def test_normalise_converts_units_and_validates():
    plan = normalise_plan(raw_plan())
    PlanJSON.model_validate(plan)
    assert plan["schema_version"] == SCHEMA_VERSION
    assert plan["units"] == "m"
    assert plan["building_type"] == "villa"
    level = plan["levels"][0]
    assert (level["index"], level["name"]) == (0, "Ground Floor Plan")
    assert level["wall_height"] == UNSTATED_WALL_HEIGHT_M
    assert level["wall_height_source"] == "default"
    bedroom = next(r for r in level["rooms"] if r["name"].startswith("BEDROOM"))
    assert bedroom["polygon"] == [[0.0, 0.0], [3.048, 0.0], [3.048, 3.048], [0.0, 3.048]]


def test_normalise_assigns_stable_ids_in_canonical_order():
    level = normalise_plan(raw_plan())["levels"][0]
    assert [r["id"] for r in level["rooms"]] == ["L0-R01", "L0-R02", "L0-R03"]
    assert [r["name"].split()[0] for r in level["rooms"]] == ["BEDROOM", "Open", "OPEN"]
    assert [w["id"] for w in level["walls"]] == [
        f"L0-W{n:02d}" for n in range(1, len(level["walls"]) + 1)
    ]
    assert [o["id"] for o in level["openings"]] == ["L0-O01", "L0-O02"]
    assert level["columns"][0]["id"] == "L0-C01"
    wall_ids = {w["id"] for w in level["walls"]}
    assert all(o["wall_id"] in wall_ids for o in level["openings"])


def test_normalise_is_independent_of_the_order_the_model_listed_things():
    shuffled = raw_plan()
    lvl = shuffled["levels"][0]
    lvl["rooms"].reverse()
    lvl["walls"].reverse()
    lvl["openings"].reverse()
    assert normalise_plan(shuffled) == normalise_plan(raw_plan())


def test_normalise_is_deterministic_and_idempotent():
    first = normalise_plan(raw_plan())
    assert normalise_plan(raw_plan()) == first
    assert json.dumps(normalise_plan(copy.deepcopy(first)), sort_keys=True) == json.dumps(
        first, sort_keys=True
    )


def test_normalise_sets_kinds_types_and_new_fields():
    level = normalise_plan(raw_plan())["levels"][0]
    kinds = {r["name"].split()[0]: r["kind"] for r in level["rooms"]}
    assert kinds == {"BEDROOM": "indoor", "Open": "indoor", "OPEN": "void"}
    assert {o["type"] for o in level["openings"]} == {"door", "window"}
    for wall in level["walls"]:
        assert wall["kind"] in ("exterior", "interior")
        assert wall["is_exterior"] is (wall["kind"] == "exterior")
    door = next(o for o in level["openings"] if o["type"] == "door")
    assert door["sill_height"] == door["sill"] == 0.0
    assert door["position"] == [3.048, 1.524]  # centre of the opening, on its wall
    window = next(o for o in level["openings"] if o["type"] == "window")
    assert window["sill_height"] == window["sill"] == 0.914


def test_normalise_keeps_a_stated_wall_height():
    raw = raw_plan()
    raw["levels"][0].update({"wall_height": 10, "wall_height_source": "stated"})
    level = normalise_plan(raw)["levels"][0]
    assert (level["wall_height"], level["wall_height_source"]) == (3.048, "stated")


def test_normalise_ignores_an_implausible_wall_height():
    raw = raw_plan()
    raw["levels"][0].update({"wall_height": 120, "wall_height_source": "stated"})
    level = normalise_plan(raw)["levels"][0]
    assert (level["wall_height"], level["wall_height_source"]) == (
        UNSTATED_WALL_HEIGHT_M,
        "default",
    )


def test_normalise_orders_levels_and_stacks_elevations():
    raw = raw_plan()
    upper = copy.deepcopy(raw["levels"][0])
    upper.update({"index": 1, "name": "First Floor Plan"})
    raw["levels"][0]["index"] = 0
    raw["levels"] = [upper, raw["levels"][0]]  # listed top floor first
    plan = normalise_plan(raw)
    assert [lvl["name"] for lvl in plan["levels"]] == ["Ground Floor Plan", "First Floor Plan"]
    assert [lvl["index"] for lvl in plan["levels"]] == [0, 1]
    assert [lvl["elevation"] for lvl in plan["levels"]] == [0.0, UNSTATED_WALL_HEIGHT_M]
    assert plan["levels"][1]["rooms"][0]["id"] == "L1-R01"


def test_scale_warnings_for_implausible_rooms():
    raw = raw_plan()
    raw["units"] = "m"  # the same numbers read as metres: rooms far larger than their labels
    raw["levels"][0]["rooms"].append(
        {
            "id": "tiny",
            "name": "STORE",
            "kind": "indoor",
            "polygon": [[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5]],
        }
    )
    warnings = normalise_plan(raw)["warnings"]
    assert any("'STORE' is only 0.25 m2" in w for w in warnings)
    assert any(
        "'BEDROOM 10' X 10'' is drawn as 100.00 m2 but its label states 9.29 m2" in w
        for w in warnings
    )


def test_scale_warning_for_an_oversized_room():
    raw = {
        "units": "m",
        "levels": [
            {
                "rooms": [
                    {
                        "id": "h",
                        "name": "HALL",
                        "kind": "indoor",
                        "polygon": [[0, 0], [30, 0], [30, 30], [0, 30]],
                    }
                ],
                "walls": [
                    {"id": "a", "start": [0, 0], "end": [30, 0], "kind": "exterior"},
                    {"id": "b", "start": [30, 0], "end": [30, 30], "kind": "exterior"},
                    {"id": "c", "start": [30, 30], "end": [0, 30], "kind": "exterior"},
                    {"id": "d", "start": [0, 30], "end": [0, 0], "kind": "exterior"},
                ],
            }
        ],
    }
    assert any("'HALL' is 900.00 m2" in w for w in normalise_plan(raw)["warnings"])


def test_a_room_outside_the_building_outline_is_dropped_with_a_warning():
    raw = raw_plan()
    raw["levels"][0]["rooms"].append(
        {
            "id": "far",
            "name": "ANNEXE",
            "kind": "indoor",
            "polygon": [[100, 100], [110, 100], [110, 110], [100, 110]],
        }
    )
    plan = normalise_plan(raw)
    assert all(r["name"] != "ANNEXE" for r in plan["levels"][0]["rooms"])
    assert any("'ANNEXE' lies outside the building outline" in w for w in plan["warnings"])


def test_no_scale_warning_when_label_and_polygon_agree():
    assert normalise_plan(raw_plan())["warnings"] == []


def test_unknown_unit_is_reported():
    raw = raw_plan()
    raw["units"] = "cubits"
    assert any("Unknown drawing unit" in w for w in normalise_plan(raw)["warnings"])


def test_room_without_an_outline_is_dropped_with_a_warning():
    raw = raw_plan()
    raw["levels"][0]["rooms"].append({"id": "bad", "name": "GHOST", "polygon": [[0, 0], [1, 1]]})
    plan = normalise_plan(raw)
    assert len(plan["levels"][0]["rooms"]) == 3
    assert any("'GHOST' has no usable outline" in w for w in plan["warnings"])


def test_normalise_rejects_a_plan_without_levels():
    with pytest.raises(ValueError, match="levels"):
        normalise_plan({"units": "m"})
    with pytest.raises(ValueError):
        normalise_plan("not a plan")


# --------------------------------------------------------------- old stored PlanJSON


def test_old_stored_plan_loads_with_defaults_filled():
    old = json.loads(EXTRACTED_PLAN.read_text(encoding="utf-8"))
    assert "schema_version" not in old
    upgraded = upgrade_plan(old)
    PlanJSON.model_validate(upgraded)
    assert upgraded["schema_version"] == SCHEMA_VERSION
    assert upgraded["building_type"] == "other"
    assert upgraded["warnings"] == []
    level, old_level = upgraded["levels"][0], old["levels"][0]
    assert (level["index"], level["name"], level["wall_height_source"]) == (
        0,
        "Ground Floor",
        "default",
    )
    # nothing that existed is renamed, reordered or re-identified
    assert [r["id"] for r in level["rooms"]] == [r["id"] for r in old_level["rooms"]]
    assert [w["id"] for w in level["walls"]] == [w["id"] for w in old_level["walls"]]
    assert [r["polygon"] for r in level["rooms"]] == [r["polygon"] for r in old_level["rooms"]]
    assert upgraded["confidence"] == old["confidence"]
    for old_wall, wall in zip(old_level["walls"], level["walls"], strict=True):
        assert wall["kind"] == old_wall["kind"]
        assert wall["is_exterior"] is (old_wall["kind"] == "exterior")
    for old_opening, opening in zip(old_level["openings"], level["openings"], strict=True):
        assert opening["offset"] == old_opening["offset"]
        assert opening["sill_height"] == opening["sill"] == old_opening["sill"]
        assert opening["position"] is not None


def test_old_plan_keys_still_validate_directly():
    """A 1.x document needs no upgrade step to pass the 2.0 model."""
    old = json.loads(EXTRACTED_PLAN.read_text(encoding="utf-8"))
    plan = PlanJSON(**old)
    assert plan.schema_version == SCHEMA_VERSION
    assert plan.levels[0].openings[0].sill_height == plan.levels[0].openings[0].sill
    assert plan.levels[0].walls[0].is_exterior is True


def test_the_full_normaliser_also_accepts_an_old_stored_plan():
    old = json.loads(EXTRACTED_PLAN.read_text(encoding="utf-8"))
    plan = normalise_plan(old)
    PlanJSON.model_validate(plan)
    assert plan["levels"][0]["rooms"][0]["id"] == "L0-R01"
    assert len(plan["levels"][0]["rooms"]) == len(old["levels"][0]["rooms"])
