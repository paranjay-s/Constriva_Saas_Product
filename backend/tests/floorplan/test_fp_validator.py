import copy

import pytest

from app.modules.ai.floorplan.pipeline.validator import ValidationReport, validate
from app.modules.ai.floorplan.schemas.plan import FloorPlan
from app.modules.ai.floorplan.schemas.program import RoomProgram


def _check(d: dict, program: RoomProgram | None = None) -> ValidationReport:
    return validate(FloorPlan.model_validate(d), program)


def _by_id(items: list[dict], item_id: str) -> dict:
    return next(i for i in items if i["id"] == item_id)


def _program_for(d: dict, **overrides) -> RoomProgram:
    """A program whose targets equal the plan's actual room areas."""
    rooms = []
    for r in d["rooms"]:
        if r["type"] in ("lobby", "foyer"):
            continue
        zone = "open" if r["type"] == "garden" else "private"
        rooms.append(
            {
                "id": r["id"],
                "type": r["type"],
                "label": r["label"],
                "target_area_m2": r["w"] * r["h"] / 10_000,
                "zone": zone,
                **overrides.get(r["id"], {}),
            }
        )
    return RoomProgram.model_validate({"rooms": rooms})


# ------------------------------------------------------------------------ valid


def test_sample_plan_is_valid(sample_dict: dict) -> None:
    rep = _check(sample_dict)
    assert rep.ok, rep.feedback()
    assert {w.code for w in rep.warnings} == {"WET_NOT_CLUSTERED"}


def test_sample_matches_its_program(sample_dict: dict) -> None:
    prog = _program_for(
        sample_dict, bath_1={"attached_to": "bed_1"}, bath_2={"attached_to": "bed_2"}
    )
    rep = _check(sample_dict, prog)
    assert rep.ok, rep.feedback()


# ------------------------------------------------------------- geometry failures


def test_overlap(sample_dict: dict) -> None:
    _by_id(sample_dict["rooms"], "bath_1")["x"] = 400
    rep = _check(sample_dict)
    assert "OVERLAP" in rep.codes()
    assert any("bed_1 and bath_1" in m for m in rep.feedback())


def test_outside_plot(sample_dict: dict) -> None:
    _by_id(sample_dict["rooms"], "garden_1")["w"] = 400  # 850 + 400 > 1200
    assert "OUTSIDE_PLOT" in _check(sample_dict).codes()


def test_below_minimum_size(sample_dict: dict) -> None:
    _by_id(sample_dict["rooms"], "dress_1")["type"] = "bedroom"  # 200 x 200
    codes = _check(sample_dict).codes()
    assert {"MIN_AREA", "MIN_SIDE"} <= codes


def test_fixture_outside_room(sample_dict: dict) -> None:
    _by_id(sample_dict["fixtures"], "f1")["x"] = 440
    assert "FIXTURE_OUTSIDE_ROOM" in _check(sample_dict).codes()


# ---------------------------------------------------------------- circulation


def test_unreachable_room(sample_dict: dict) -> None:
    sample_dict["doors"] = [d for d in sample_dict["doors"] if d["id"] != "d6"]
    rep = _check(sample_dict)
    assert rep.codes() == {"UNREACHABLE"}
    assert rep.errors[0].ids == ("store_1",)


def test_no_entrance(sample_dict: dict) -> None:
    sample_dict["doors"] = [d for d in sample_dict["doors"] if d["id"] not in ("d1", "d15")]
    codes = _check(sample_dict).codes()
    assert "NO_ENTRANCE" in codes and "UNREACHABLE" in codes


def test_entrance_through_open_garden_is_enough(sample_dict: dict) -> None:
    sample_dict["doors"] = [d for d in sample_dict["doors"] if d["id"] != "d1"]
    assert _check(sample_dict).ok


def test_missing_attached_bath(sample_dict: dict) -> None:
    # bath_1 now opens from the dress room instead of the bedroom: reachable, not attached
    d7 = _by_id(sample_dict["doors"], "d7")
    d7.update({"from": "dress_1", "wall": "south", "offset": 60})
    prog = _program_for(sample_dict, bath_1={"attached_to": "bed_1"})
    rep = _check(sample_dict, prog)
    assert rep.codes() == {"ATTACHED_BATH"}
    assert rep.errors[0].ids == ("bath_1", "bed_1")


# ------------------------------------------------------------------- openings


def test_window_on_internal_wall(sample_dict: dict) -> None:
    sample_dict["windows"].append(
        {"id": "w99", "room": "bed_1", "wall": "east", "offset": 300, "width": 100}
    )
    rep = _check(sample_dict)
    assert rep.codes() == {"WINDOW_NOT_EXTERIOR"}


def test_window_too_close_to_corner(sample_dict: dict) -> None:
    _by_id(sample_dict["windows"], "w12")["offset"] = 555  # within 12 cm of the foyer wall
    assert "WINDOW_NOT_EXTERIOR" in _check(sample_dict).codes()


def test_door_wider_than_shared_wall(sample_dict: dict) -> None:
    d12 = _by_id(sample_dict["doors"], "d12")  # bed_3 and living share only 150 cm
    d12.update({"offset": 300, "width": 140})
    assert "DOOR_TOO_WIDE" in _check(sample_dict).codes()


def test_door_runs_past_wall_end(sample_dict: dict) -> None:
    _by_id(sample_dict["doors"], "d1").update({"offset": 200, "width": 100})  # foyer is 250 wide
    assert "DOOR_TOO_WIDE" in _check(sample_dict).codes()


def test_door_on_wall_not_shared_with_from_room(sample_dict: dict) -> None:
    _by_id(sample_dict["doors"], "d6")["wall"] = "north"  # store north wall faces bath_2
    assert "DOOR_NOT_ON_SHARED_WALL" in _check(sample_dict).codes()


def test_entrance_door_on_internal_wall(sample_dict: dict) -> None:
    _by_id(sample_dict["doors"], "d1").update({"wall": "north", "offset": 100})
    assert "DOOR_NOT_ON_SHARED_WALL" in _check(sample_dict).codes()


def test_door_too_narrow(sample_dict: dict) -> None:
    _by_id(sample_dict["doors"], "d7")["width"] = 60
    assert "DOOR_TOO_NARROW" in _check(sample_dict).codes()


# -------------------------------------------------------------------- program


def test_area_mismatch(sample_dict: dict) -> None:
    prog = _program_for(sample_dict, bed_2={"target_area_m2": 30.0})
    rep = _check(sample_dict, prog)
    assert "AREA_MISMATCH" in rep.codes()
    assert any("bed_2 is 18.0 m2, target 30.0 m2" in m for m in rep.feedback())


def test_total_area_mismatch(sample_dict: dict) -> None:
    prog = _program_for(sample_dict)
    for r in prog.rooms:
        r.target_area_m2 *= 1.3
    assert "TOTAL_AREA_MISMATCH" in _check(sample_dict, prog).codes()


def test_program_room_missing_and_type_mismatch(sample_dict: dict) -> None:
    prog = _program_for(sample_dict, bed_3={"type": "study"})
    prog.rooms.append(prog.rooms[0].model_copy(update={"id": "bed_9"}))
    codes = _check(sample_dict, prog).codes()
    assert {"PROGRAM_MISSING_ROOM", "PROGRAM_TYPE_MISMATCH"} <= codes


# ------------------------------------------------------------------- warnings


def test_gaps_are_a_warning_not_an_error() -> None:
    plan = {
        "id": "p",
        "plot": {"width": 1000, "depth": 1000},
        "rooms": [
            {"id": "r", "type": "living", "label": "LIVING", "x": 0, "y": 0, "w": 400, "h": 400}
        ],
        "doors": [
            {"id": "d", "from": None, "to": "r", "wall": "north", "offset": 100, "width": 90}
        ],
    }
    rep = _check(plan)
    assert rep.ok
    assert {w.code for w in rep.warnings} == {"PLOT_GAPS"}


@pytest.mark.parametrize("room_id", ["bath_1", "kitchen_1"])
def test_isolated_wet_rooms_get_warning(sample_dict: dict, room_id: str) -> None:
    rep = _check(copy.deepcopy(sample_dict))
    assert any(room_id in w.ids for w in rep.warnings)


def test_feedback_lines_are_exact(sample_dict: dict) -> None:
    sample_dict["doors"] = [d for d in sample_dict["doors"] if d["id"] != "d6"]
    assert _check(sample_dict).feedback() == [
        "UNREACHABLE: store_1 cannot be reached through doors from the entrance"
    ]
