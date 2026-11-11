"""
=============================================================================
Construtiva Bill of Materials (BOQ) Unit & Export Test Suite
=============================================================================
File: tests/unit/test_sheets.py
Purpose:
  Verifies the complete lifecycle and document generation of the Sheets module:
  - Validates catalogue retrieval for the 7 standard construction materials.
  - Tests sheet initialization, item additions, inline edits, and deletions.
  - Tests CSV byte export generation.
  - Tests ReportLab PDF byte export generation.
=============================================================================
"""

import os
os.environ["TESTING"] = "1"

import pytest
from app.modules.sheets.service import SheetService, DEFAULT_CONSTRUCTION_MATERIALS
from app.modules.sheets.export import generate_sheet_csv, generate_sheet_pdf, HAS_REPORTLAB
from app.modules.sheets.schemas import (
    SheetItemCreate,
    SheetItemUpdate,
)


def test_material_catalogue_contains_all_7_materials():
    """
    Ensures the master catalogue includes all 7 materials requested by the user:
    1. Brick
    2. Steel/rebar rod
    3. Cement
    4. Sand (fine aggregate)
    5. Ballast (coarse aggregate)
    6. Plaster (cement and gypsum)
    7. Tiles (floor and wall)
    """
    catalogue = SheetService.get_material_catalogue()
    assert len(catalogue) == 7

    names = [m["name"] for m in catalogue]
    expected_materials = [
        "Brick",
        "Steel/rebar rod",
        "Cement",
        "Sand (fine aggregate)",
        "Ballast (coarse aggregate)",
        "Plaster (cement and gypsum)",
        "Tiles (floor and wall)",
    ]

    for expected in expected_materials:
        assert expected in names, f"Missing material: {expected}"

    for m in catalogue:
        assert m.get("id") is not None, f"Material {m['name']} must have a non-null id"
        assert len(m["id"]) == 36, f"Material {m['name']} id must be a valid 36-char UUID string"


def test_generate_sheet_csv_output():
    """
    Tests that generate_sheet_csv produces valid UTF-8 CSV content with header and items.
    """
    sample_sheet = {
        "name": "Cost Estimate",
        "currency": "INR",
        "subtotal": 500000.0,
        "contingency_rate": 0.05,
        "contingency": 25000.0,
        "total_cost": 525000.0,
        "items": [
            {
                "name": "Brick",
                "category": "Masonry",
                "unit": "pcs",
                "quantity": 8500.0,
                "waste_factor": 0.05,
                "total_quantity": 8925.0,
                "unit_price": 9.50,
                "amount": 84787.50,
                "surface_tag": "masonry_walls",
            },
            {
                "name": "Steel/rebar rod",
                "category": "Structural Steel",
                "unit": "kg",
                "quantity": 2800.0,
                "waste_factor": 0.03,
                "total_quantity": 2884.0,
                "unit_price": 68.00,
                "amount": 196112.00,
                "surface_tag": "structural_reinforcement",
            },
        ],
    }

    csv_bytes = generate_sheet_csv(sample_sheet, project_name="Pavilion Serena")
    csv_text = csv_bytes.decode("utf-8")

    assert "CONSTRUTIVA - BILL OF MATERIALS (BOQ)" in csv_text
    assert "Pavilion Serena" in csv_text
    assert "Brick" in csv_text
    assert "Steel/rebar rod" in csv_text
    assert "Area (m²)" in csv_text
    assert "Total Qty" in csv_text
    assert "Rate (INR)" not in csv_text
    assert "Amount (INR)" not in csv_text


@pytest.mark.skipif(not HAS_REPORTLAB, reason="ReportLab is not installed in the environment")
def test_generate_sheet_pdf_output():
    """
    Tests that generate_sheet_pdf creates valid binary PDF bytes using ReportLab.
    """
    sample_sheet = {
        "name": "Cost Estimate",
        "currency": "INR",
        "subtotal": 600000.0,
        "contingency_rate": 0.05,
        "contingency": 30000.0,
        "total_cost": 630000.0,
        "items": [
            {
                "name": mat["name"],
                "category": mat["category"],
                "unit": mat["unit"],
                "quantity": mat["default_quantity"],
                "waste_factor": mat["waste_factor"],
                "total_quantity": mat["default_quantity"] * (1.0 + mat["waste_factor"]),
                "unit_price": mat["unit_price"],
                "amount": mat["default_quantity"] * (1.0 + mat["waste_factor"]) * mat["unit_price"],
                "surface_tag": mat["surface_tag"],
            }
            for mat in DEFAULT_CONSTRUCTION_MATERIALS
        ],
    }

    pdf_bytes = generate_sheet_pdf(sample_sheet, project_name="Pavilion Serena")

    # Verify standard PDF magic bytes (%PDF)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000  # ReportLab table with styles generates a solid PDF document


def test_map_plan_to_materials_smt_geeta_gaud():
    """
    Mandatory Verification Test (Task 2):
    Feeds SMT. GEETA GAUD (36'6" X 55' (E) AT SHALIMAR GREENS) PlanJSON
    into map_plan_to_materials() and verifies all exact QS geometric and material quantities.
    """
    import json
    from pathlib import Path
    from app.modules.sheets.llm_mapper import map_plan_to_materials

    plan_path = Path(__file__).resolve().parents[2] / "extracted_plan.json"
    assert plan_path.exists(), "extracted_plan.json must exist in backend directory"

    with open(plan_path, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    result = map_plan_to_materials(plan_data)

    geo = result["geometry_summary"]
    mats = result["materials_by_key"]

    # 1. Geometric base assertions
    assert geo["a_built_total_m2"] == 159.62
    assert geo["a_net_wall_m2"] == 519.08
    assert geo["a_total_masonry_m2"] == 699.39

    # 2. The 7 Core Materials Exact Assertions
    # AAC Blocks & Bricks
    assert mats["aac_blocks"]["quantity"] == 6120
    assert mats["aac_blocks"]["unit"] == "pieces"
    assert mats["aac_blocks"]["details"]["india_clay_bricks_equivalent"] == 40390

    # Steel Rebar
    assert mats["steel_rebar"]["quantity"] == 9.83
    assert mats["steel_rebar"]["unit"] == "metric_tons"
    assert mats["steel_rebar"]["secondary_quantity"] == 923
    assert mats["steel_rebar"]["secondary_unit"] == "rods_12m"

    # Cement
    assert mats["cement"]["quantity"] == 337
    assert mats["cement"]["unit"] == "bags_50kg"

    # Sand
    assert mats["sand"]["quantity"] == 47.74
    assert mats["sand"]["unit"] == "metric_tons"
    assert mats["sand"]["secondary_quantity"] == 29.33
    assert mats["sand"]["secondary_unit"] == "m3"

    # Ballast / Gitti
    assert mats["ballast_gitti"]["quantity"] == 32.79
    assert mats["ballast_gitti"]["unit"] == "metric_tons"
    assert mats["ballast_gitti"]["secondary_quantity"] == 21.86
    assert mats["ballast_gitti"]["secondary_unit"] == "m3"

    # Plaster
    assert mats["plaster"]["quantity"] == 348
    assert mats["plaster"]["unit"] == "bags_30kg"
    assert mats["plaster"]["details"]["external_wet_cement_plaster_area_m2"] == 363.36

    # Tiles
    assert mats["tiles"]["quantity"] == 534
    assert mats["tiles"]["unit"] == "pieces"
    assert mats["tiles"]["secondary_quantity"] == 192.17
    assert mats["tiles"]["secondary_unit"] == "m2"

    # 3. Room Breakdown Assertions
    rooms = result["room_breakdown"]
    assert len(rooms) == 23

    # Check L-shaped rooms
    master_bed = next(r for r in rooms if r["id"] == "room_bed_master_left")
    assert master_bed["vertices_count"] == 6
    assert master_bed["is_complex_polygon"] is True

    drg_right = next(r for r in rooms if r["id"] == "room_drg_right")
    assert drg_right["vertices_count"] == 6
    assert drg_right["is_complex_polygon"] is True

    # Check outdoor lawn and open void shaft (zero structural materials)
    lawn = next(r for r in rooms if r["id"] == "room_lawn")
    assert lawn["materials_by_key"]["aac_blocks"]["quantity"] == 0
    assert lawn["materials_by_key"]["steel_rebar"]["quantity"] == 0.0

    shaft = next(r for r in rooms if r["id"] == "room_open_shaft")
    assert shaft["materials_by_key"]["aac_blocks"]["quantity"] == 0
    assert shaft["materials_by_key"]["steel_rebar"]["quantity"] == 0.0

    # Check 3D highlighting metadata presence
    assert "surface_tag" in mats["aac_blocks"]
    assert "highlight_3d" in mats["aac_blocks"]
    assert len(mats["aac_blocks"]["highlight_3d"]["room_ids"]) > 0


def test_3d_highlight_metadata_on_all_materials():
    """
    Verifies that all 7 materials have valid surface_tag and highlight_3d payloads
    enabling real-time Three.js highlighting on user click.
    """
    import json
    from pathlib import Path
    from app.modules.sheets.llm_mapper import map_plan_to_materials

    plan_path = Path(__file__).resolve().parents[2] / "extracted_plan.json"
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    result = map_plan_to_materials(plan_data)
    mats = result["materials_by_key"]

    expected_tags = {
        "aac_blocks": "masonry_walls",
        "steel_rebar": "structural_reinforcement",
        "cement": "concrete_and_mortar",
        "sand": "fine_aggregate",
        "ballast_gitti": "coarse_aggregate",
        "plaster": "wall_plaster",
        "tiles": "flooring_and_skirting",
    }

    for mat_key, expected_tag in expected_tags.items():
        mat = mats[mat_key]
        assert mat["surface_tag"] == expected_tag
        assert "highlight_3d" in mat
        assert "target" in mat["highlight_3d"]
        assert "color" in mat["highlight_3d"]
        assert isinstance(mat["highlight_3d"]["room_ids"], list)


def test_sheet_item_edit_schemas():
    """
    Verifies that SheetItemUpdate schema validates partial edits correctly.
    """
    update = SheetItemUpdate(
        quantity=500.0,
        unit_price=420.0,
        waste_factor=0.08,
    )
    assert update.quantity == 500.0
    assert update.unit_price == 420.0
    assert update.waste_factor == 0.08


def test_prepare_db_item_conforms_to_supabase_schema():
    """
    Verifies that _prepare_db_item emits exact columns matching the Supabase
    public.sheet_items schema (id, sheet_id, quantity, unit, unit_price,
    currency, source, user_overridden, detail) and does NOT leak unmapped
    columns (name, category, amount, waste_factor) that trigger PGRST204 errors.
    """
    sheet_id = "test-sheet-uuid-001"
    item = SheetService._prepare_db_item(
        sheet_id=sheet_id,
        name="TMT Steel 12mm",
        category="Structural Steel",
        unit="kg",
        quantity=1000.0,
        waste_factor=0.05,
        unit_price=68.0,
        surface_tag="structural_reinforcement",
        is_custom=False,
    )

    # Allowed columns in public.sheet_items
    allowed_cols = {
        "id", "sheet_id", "material_id", "quantity", "unit",
        "unit_price", "currency", "source", "user_overridden", "detail"
    }
    assert set(item.keys()).issubset(allowed_cols)

    # Verify JSONB detail packaging
    detail = item["detail"]
    assert detail["name"] == "TMT Steel 12mm"
    assert detail["category"] == "Structural Steel"
    assert detail["total_quantity"] == 1050.0
    assert detail["amount"] == 71400.0
    assert detail["surface_tag"] == "structural_reinforcement"
    assert detail["is_custom"] is False


def test_normalize_sheet_item_unpacks_detail():
    """
    Verifies that _normalize_sheet_item unpacks JSONB detail fields into
    standard top-level dictionary keys expected by SheetItemResponse and PDF exports.
    """
    raw_db_row = {
        "id": "item-uuid-123",
        "sheet_id": "sheet-uuid-456",
        "quantity": 1050.0,
        "unit": "kg",
        "unit_price": 68.0,
        "currency": "INR",
        "source": "calculated",
        "user_overridden": False,
        "detail": {
            "name": "Steel Rebar",
            "category": "Structure",
            "quantity": 1000.0,
            "waste_factor": 0.05,
            "total_quantity": 1050.0,
            "unit_price": 68.0,
            "amount": 71400.0,
            "surface_tag": "structural_reinforcement",
            "is_custom": False,
        }
    }

    normalized = SheetService._normalize_sheet_item(raw_db_row)
    assert normalized["name"] == "Steel Rebar"
    assert normalized["category"] == "Structure"
    assert normalized["quantity"] == 1000.0
    assert normalized["waste_factor"] == 0.05
    assert normalized["total_quantity"] == 1050.0
    assert normalized["amount"] == 71400.0
    assert normalized["surface_tag"] == "structural_reinforcement"
    assert normalized["is_custom"] is False


def test_pdf_export_with_contingency_amount_schema():
    """
    Verifies that PDF export works cleanly when the sheet dictionary only has
    the DB schema columns 'contingency_percent' and 'contingency_amount'.
    """
    sheet_from_db = {
        "id": "sheet-uuid-001",
        "name": "BOQ Report",
        "subtotal": 100000.0,
        "contingency_percent": 5.0,
        "contingency_amount": 5000.0,
        "total_cost": 105000.0,
        "currency": "INR",
        "items": [
            {
                "name": "Cement",
                "category": "Binder",
                "unit": "bags",
                "quantity": 100.0,
                "waste_factor": 0.02,
                "total_quantity": 102.0,
                "unit_price": 380.0,
                "amount": 38760.0,
                "surface_tag": "concrete_and_mortar",
            }
        ]
    }

    pdf_bytes = generate_sheet_pdf(sheet_from_db, project_name="Test Project")
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_get_or_create_sheet_includes_plan_id_in_insert(monkeypatch):
    """
    Verifies that get_or_create_sheet queries the active plan and includes 'plan_id'
    in the new_sheet row to satisfy the NOT NULL constraint on public.sheets(plan_id).
    """
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    inserted_rows = []

    # Mock table("sheets").select("*").eq("project_id", ...).execute() -> empty (sheet doesn't exist yet)
    sheets_query = MagicMock()
    sheets_query.select.return_value.eq.return_value.execute.return_value.data = []

    # Capture insert
    def mock_insert(row):
        inserted_rows.append(row)
        res = MagicMock()
        res.execute.return_value.data = [row]
        return res
    sheets_query.insert = mock_insert

    # Mock table("plans").select("id").eq("project_id", ...).order(...).limit(1).execute() -> returns plan_id
    plans_query = MagicMock()
    plans_query.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"id": "plan-uuid-5555", "plan_json": {}}
    ]

    # Mock sheet_items
    items_query = MagicMock()
    items_query.insert.return_value.execute.return_value.data = []
    items_query.select.return_value.eq.return_value.execute.return_value.data = []
    items_query.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

    def mock_table(table_name):
        if table_name == "sheets":
            return sheets_query
        elif table_name == "plans":
            return plans_query
        elif table_name == "sheet_items":
            return items_query
        return MagicMock()

    mock_client.table = mock_table
    monkeypatch.setattr("app.modules.sheets.service.get_supabase_client", lambda: mock_client)

    result_sheet = SheetService.get_or_create_sheet("project-uuid-9999")

    # Assert new sheet row was inserted with valid plan_id
    assert len(inserted_rows) == 1
    new_sheet = inserted_rows[0]
    assert new_sheet["plan_id"] == "plan-uuid-5555"
    assert new_sheet["project_id"] == "project-uuid-9999"
    assert "contingency_percent" in new_sheet
    assert "contingency_amount" in new_sheet


def test_surface_mappings_query_and_update(monkeypatch):
    """
    Verifies that get_surface_mappings and update_surface_mappings correctly use
    'plan_id' and 'element_id' matching the public.material_mappings schema.
    """
    from unittest.mock import MagicMock
    mock_client = MagicMock()

    # Mock plans table lookup
    plans_query = MagicMock()
    plans_query.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"id": "plan-uuid-1234"}
    ]

    # Mock material_mappings table
    mappings_query = MagicMock()
    mappings_query.select.return_value.eq.return_value.execute.return_value.data = [
        {
            "id": "map-1",
            "plan_id": "plan-uuid-1234",
            "material_id": "mat-1",
            "element_id": "masonry_walls",
            "mapping_data": {"surface_tag": "masonry_walls", "material_name": "Brick"},
            "materials": {"name": "Brick", "category": "Masonry", "unit": "pcs"}
        }
    ]

    def mock_table(table_name):
        if table_name == "plans":
            return plans_query
        elif table_name == "material_mappings":
            return mappings_query
        return MagicMock()

    mock_client.table = mock_table
    monkeypatch.setattr("app.modules.sheets.service.get_supabase_client", lambda: mock_client)

    res = SheetService.get_surface_mappings("proj-1234")
    assert len(res) == 1
    assert res[0]["surface_tag"] == "masonry_walls"
    assert res[0]["material_name"] == "Brick"
    assert res[0]["plan_id"] == "plan-uuid-1234"
    assert "unit_price" not in res[0]
    assert "amount" not in res[0]
    assert "unit_price" not in res[0]["mapping_data"]
    assert "amount" not in res[0]["mapping_data"]
    assert "unit_price" not in res[0]["materials"]
    assert "amount" not in res[0]["materials"]
    assert "quantity" in res[0]
    assert "area" in res[0]


def test_default_boq_items_contains_all_7_materials():
    """
    Verifies that get_default_boq_items produces all 7 materials with positive quantities,
    surface tags, and calibrated geometric properties for instant failsafe reporting.
    """
    items = SheetService.get_default_boq_items()
    assert len(items) == 7
    expected_materials = [
        "Brick",
        "Steel/rebar rod",
        "Cement",
        "Sand (fine aggregate)",
        "Ballast (coarse aggregate)",
        "Plaster (cement and gypsum)",
        "Tiles (floor and wall)",
    ]
    names = [m["name"] for m in items]
    for expected in expected_materials:
        assert expected in names
    for item in items:
        assert item["quantity"] > 0
        assert item["surface_tag"] is not None
        assert item["total_quantity"] >= item["quantity"]






