import pytest
from pydantic import TypeAdapter, ValidationError

from app.modules.ai.floorplan.schemas import Brief, EditOp, FloorPlan, RoomProgram
from app.modules.ai.floorplan.units import fmt_area, fmt_size, ft_in, to_cm


def test_sample_plan_loads(sample_plan: FloorPlan) -> None:
    assert len(sample_plan.rooms) == 15
    assert sample_plan.room("bed_1").area_m2 == 20.25
    assert sample_plan.room("garden_1").is_open
    # built area excludes the open garden (350 x 400)
    assert sample_plan.built_area_m2 == round(180.0 - 14.0, 1)


def test_door_alias_round_trip(sample_plan: FloorPlan) -> None:
    data = sample_plan.to_json_dict()
    assert data["doors"][0]["from"] is None
    assert data["doors"][1]["from"] == "foyer_1"
    assert FloorPlan.model_validate(data) == sample_plan


def test_duplicate_ids_rejected(sample_dict: dict) -> None:
    sample_dict["rooms"][1]["id"] = "bed_1"
    with pytest.raises(ValidationError, match="duplicate ids"):
        FloorPlan.model_validate(sample_dict)


def test_unknown_room_reference_rejected(sample_dict: dict) -> None:
    sample_dict["windows"][0]["room"] = "nope"
    with pytest.raises(ValidationError, match="unknown rooms"):
        FloorPlan.model_validate(sample_dict)


def test_negative_and_zero_geometry_rejected(sample_dict: dict) -> None:
    sample_dict["rooms"][0]["w"] = 0
    with pytest.raises(ValidationError):
        FloorPlan.model_validate(sample_dict)


def test_unknown_fields_rejected(sample_dict: dict) -> None:
    sample_dict["rooms"][0]["colour"] = "red"
    with pytest.raises(ValidationError):
        FloorPlan.model_validate(sample_dict)


def test_meta_defaults_have_no_names() -> None:
    plan = FloorPlan.model_validate({"id": "p", "plot": {"width": 100, "depth": 100}})
    assert plan.meta.project == "" and plan.meta.owner == ""


def test_edit_ops_discriminated() -> None:
    ops = TypeAdapter(list[EditOp]).validate_python(
        [
            {"op": "resize_room", "id": "bed_1", "width_cm": 420, "height_cm": 480},
            {"op": "move_room", "id": "kitchen_1", "anchor": "east"},
            {"op": "add_room", "type": "store"},
        ]
    )
    assert [o.op for o in ops] == ["resize_room", "move_room", "add_room"]
    with pytest.raises(ValidationError):
        TypeAdapter(list[EditOp]).validate_python([{"op": "teleport", "id": "x"}])


def test_brief_and_program_minimal() -> None:
    brief = Brief.model_validate({"plot": {"width_cm": 1200, "depth_cm": 1500}})
    assert brief.bedrooms is None and brief.unknowns == []
    prog = RoomProgram.model_validate(
        {
            "rooms": [
                {
                    "id": "bed_1",
                    "type": "bedroom",
                    "label": "BED ROOM",
                    "target_area_m2": 14,
                    "zone": "private",
                }
            ]
        }
    )
    assert prog.rooms[0].attached_to is None


def test_units() -> None:
    assert to_cm(10, "ft") == 305
    assert to_cm(4.5, "m") == 450
    assert fmt_size(400, 500, "cm") == "400X500"
    assert fmt_size(400, 500, "m") == "4.00X5.00"
    assert ft_in(400) == "13'1\""
    assert ft_in(30.48 * 12) == "12'"
    assert fmt_area(251.7, "cm") == "251.7 M2"
    assert fmt_area(100, "ft") == "1,076 SQ.FT"
