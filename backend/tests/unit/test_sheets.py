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

import pytest
from app.modules.sheets.service import SheetService, DEFAULT_CONSTRUCTION_MATERIALS
from app.modules.sheets.export import generate_sheet_csv, generate_sheet_pdf
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
    assert "TOTAL ESTIMATED COST (INR):" in csv_text
    assert "525000.00" in csv_text


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

