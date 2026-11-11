"""
=============================================================================
Construtiva AI 2D Floor Plan Generator Unit Tests
=============================================================================
File: tests/unit/test_ai_floorplan.py
Purpose:
  Tests parameter synthesis, high-resolution PNG rendering, PlanJSON export,
  and REST endpoints for the 2D architectural blueprint generation engine.
=============================================================================
"""

import pytest
from app.modules.ai.floorplan_generator import (
    create_architectural_template,
    render_floorplan_to_png,
    build_plan_json_from_template,
    generate_ai_floorplan,
)


def test_create_architectural_template_rental():
    """
    Verifies that rental mode produces a dual 2-BHK apartment layout
    with 18+ calibrated rooms matching Vikas Patodi Shalimar Greens plans.
    """
    plan = create_architectural_template(36.5, 55.0, config_type="dual_rental_2bhk", goal="rental", facing="East")
    assert plan["plot_width_ft"] == 36.5
    assert plan["plot_length_ft"] == 55.0
    assert len(plan["rooms"]) >= 15

    room_names = [r["name"] for r in plan["rooms"]]
    assert any("VERANDAH" in n for n in room_names)
    assert any("LAWN" in n for n in room_names)
    assert any("DRG" in n for n in room_names)
    assert any("KIT" in n for n in room_names)
    assert any("TOI" in n for n in room_names)
    assert any("WASH" in n for n in room_names)
    assert any("PASSAGE" in n for n in room_names)


def test_create_architectural_template_residence():
    """
    Verifies that residence mode produces an integrated family residence
    with luxury master suite, parking, puja room, drawing room and lawn.
    """
    plan = create_architectural_template(40.0, 60.0, config_type="3_bhk", goal="residence", facing="North")
    assert plan["plot_width_ft"] == 40.0
    assert plan["plot_length_ft"] == 60.0

    room_names = [r["name"] for r in plan["rooms"]]
    assert any("PARKING" in n for n in room_names)
    assert any("PUJA" in n for n in room_names)
    assert any("MASTER BEDROOM" in n for n in room_names)
    assert any("CHILD BEDROOM" in n for n in room_names)
    assert any("LIV" in n for n in room_names)


def test_render_floorplan_to_png_output():
    """
    Verifies that render_floorplan_to_png generates valid, non-empty PNG bytes
    with standard PNG magic bytes header.
    """
    plan = create_architectural_template(36.5, 55.0, config_type="dual_rental_2bhk", goal="rental", facing="East")
    png_bytes = render_floorplan_to_png(plan, client_name="SMT. GEETA GAUD")
    assert isinstance(png_bytes, bytes)
    assert len(png_bytes) > 10000  # High-resolution architectural drawing
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_build_plan_json_from_template():
    """
    Verifies that PlanJSON generated from template complies with standard schema
    and contains levels, walls, rooms, and openings for 3D viewer integration.
    """
    plan = create_architectural_template(36.5, 55.0, config_type="dual_rental_2bhk", goal="rental", facing="East")
    plan_json = build_plan_json_from_template(plan)
    assert plan_json["version"] == 1
    assert plan_json["units"] == "m"
    assert len(plan_json["levels"]) == 1

    level = plan_json["levels"][0]
    assert len(level["rooms"]) >= 15
    assert len(level["walls"]) >= 4
    assert len(level["openings"]) >= 1


def test_generate_ai_floorplan_pipeline():
    """
    Verifies the end-to-end generate_ai_floorplan pipeline.
    """
    result = generate_ai_floorplan(
        plot_width_ft=30.0,
        plot_length_ft=50.0,
        config_type="2_bhk",
        goal="residence",
        facing="East",
        user_prompt="Master bedroom with attached toilet and 5ft lawn in front",
        client_name="DEMO ARCHITECT",
    )
    assert "plan_id" in result
    assert "png_base64" in result
    assert len(result["png_base64"]) > 500
    assert "plan_json" in result
    assert "ai_commentary" in result
    assert len(result["rooms"]) > 5


def test_ai_generate_and_chat_endpoints():
    """
    Verifies that AI floorplan generation and conversational chat refinement
    produce complete plan payloads with CAD PNG base64 and 3D PlanJSON geometry.
    """
    # 1. Test generate-plan pipeline
    req = {
        "plot_width_ft": 36.5,
        "plot_length_ft": 55.0,
        "goal": "rental",
        "config_type": "dual_rental_2bhk",
        "facing": "East",
        "client_name": "SMT. GEETA GAUD",
        "user_prompt": "Dual 2-BHK apartments for rental income with front verandah and lawn",
    }
    data = generate_ai_floorplan(**req)
    assert "plan_id" in data
    assert "png_base64" in data
    assert len(data["png_base64"]) > 1000
    assert "rooms" in data
    assert len(data["rooms"]) >= 15
    level0 = data["plan_json"]["levels"][0]
    assert len(level0["walls"]) >= 20
    assert len(level0["openings"]) >= 10
    plan_id = data["plan_id"]

    # 2. Test chat refinement modification
    chat_data = generate_ai_floorplan(
        plot_width_ft=36.5,
        plot_length_ft=55.0,
        goal="rental",
        config_type="dual_rental_2bhk",
        facing="East",
        user_prompt="Add an attached toilet to the child bedroom and widen the passage",
        client_name="SMT. GEETA GAUD",
        project_id=plan_id,
    )
    assert "plan_id" in chat_data
    assert "png_base64" in chat_data
    assert "ai_commentary" in chat_data
    assert len(chat_data["rooms"]) >= 15
    assert len(chat_data["plan_json"]["levels"][0]["walls"]) >= 20

    # 3. Test dynamic conversion from 3 bedrooms to 2 bedrooms via chat
    reconfig_data = generate_ai_floorplan(
        plot_width_ft=36.5,
        plot_length_ft=55.0,
        goal="residence",
        config_type="3_bhk",
        facing="East",
        user_prompt="make it 2 bedrooms from 3",
        client_name="SMT. GEETA GAUD",
    )
    assert reconfig_data["config_type"] == "2_bhk"
    room_names = [r["name"] for r in reconfig_data["rooms"]]
    bedroom_count = sum(1 for r in reconfig_data["rooms"] if r.get("category") == "Bedroom")
    assert bedroom_count == 2
    assert any("FAMILY LOUNGE" in n for n in room_names)
    assert not any("CHILD BEDROOM" in n for n in room_names)
    assert "2-BHK" in reconfig_data["name"] or "2-bhk" in reconfig_data["name"].lower()


def test_extract_user_architectural_intent():
    """
    Verifies that natural language user requests correctly extract intent
    for BHK count, goal, dimensions, and orientation.
    """
    from app.modules.ai.floorplan_generator import extract_user_architectural_intent

    # Test 1: "make it 2 bedrooms from 3"
    cfg, goal, w, l, f = extract_user_architectural_intent("make it 2 bedrooms from 3", current_config="3_bhk")
    assert cfg == "2_bhk"
    assert goal == "residence"

    # Test 2: "change to rental units"
    cfg, goal, w, l, f = extract_user_architectural_intent("can we make this a rental with 2 flats?", current_config="3_bhk")
    assert goal == "rental"
    assert cfg == "dual_rental_2bhk"

    # Test 3: Plot dimensions and facing
    cfg, goal, w, l, f = extract_user_architectural_intent("plot is 40x60 facing North")
    assert w == 40.0
    assert l == 60.0
    assert f == "North"


