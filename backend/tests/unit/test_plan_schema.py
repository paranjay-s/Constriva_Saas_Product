import json
from pathlib import Path
from app.modules.plans.schemas import PlanJSON
from app.modules.parsing.validate import (
    validate_bounding_box,
    validate_y_axis_orientation,
    validate_room_dimensions_vs_labels,
    validate_l_shaped_rooms,
    validate_overlaps_and_gaps,
    validate_wall_connectivity,
    validate_openings,
    validate_room_wall_coverage,
    compute_plan_confidence,
)


def test_empty_plan_is_valid() -> None:
    plan = PlanJSON()
    assert plan.units == "m"
    assert plan.levels == []


def test_extracted_plan_json_matches_complete_blueprint() -> None:
    plan_path = Path(__file__).resolve().parents[2] / "extracted_plan.json"
    assert plan_path.exists(), "extracted_plan.json must exist in backend directory"

    with open(plan_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validates against official Pydantic schema
    plan = PlanJSON(**data)
    assert plan.units == "m"
    assert len(plan.levels) == 1

    level = plan.levels[0]
    # Check spaces, walls, openings, and columns
    assert len(level.rooms) >= 22
    assert len(level.walls) >= 30
    assert len(level.openings) == 27  # 13 architectural windows + 14 inferred doors
    assert len(level.columns) == 25   # Blue structural columns

    # Check key rooms
    room_names = [r.name.lower() for r in level.rooms]
    assert any("verandah" in n for n in room_names)
    assert any("lawn" in n for n in room_names)
    assert any("staircase" in n for n in room_names)
    assert any("bed" in n for n in room_names)
    assert any("kit" in n for n in room_names)
    assert any("drg" in n or "drawing" in n for n in room_names)
    assert any("toilet" in n or "toi" in n for n in room_names)
    assert any("passage" in n for n in room_names)

    # Check explicit kind fields
    for w in level.walls:
        assert w.kind in ("exterior", "interior")
    for r in level.rooms:
        assert r.kind in ("indoor", "semi_open", "outdoor", "void")

    # Check inferred doors
    doors = [op for op in level.openings if op.type == "door"]
    assert len(doors) == 14
    assert all(d.inferred for d in doors)

    # Check windows
    windows = [op for op in level.openings if op.type == "window"]
    assert len(windows) == 13
    assert not any(w.inferred for w in windows)

    # Run full architectural validator suite
    bb = validate_bounding_box(data)
    assert bb["passed"]

    orient = validate_y_axis_orientation(data)
    assert orient["passed"]

    labels = validate_room_dimensions_vs_labels(data)
    assert labels["passed"]

    l_shapes = validate_l_shaped_rooms(data)
    assert l_shapes["passed"]

    overlaps = validate_overlaps_and_gaps(data)
    assert overlaps["passed"]

    conn = validate_wall_connectivity(data)
    assert conn["passed"]

    openings_val = validate_openings(data)
    assert openings_val["passed"]

    cov = validate_room_wall_coverage(data)
    assert cov["passed"]

    # Check computed confidence (honest ~0.70 - 0.80 range, not hardcoded 0.98)
    conf = compute_plan_confidence(data)
    assert 0.65 <= conf["overall"] <= 0.85
