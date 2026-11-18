"""BOQ rows, the BOQ endpoints (with a fake plan parser) and the PDF / Excel exports."""

import io
import json
import time
from datetime import date
from pathlib import Path

import pymupdf
import pytest
from openpyxl import load_workbook

from app.modules.parsing.errors import PlanOutputInvalidError
from app.modules.sheets import constants
from app.modules.sheets.boq_export import (
    COLUMNS,
    FOOTER_TEXT,
    build_boq_pdf,
    build_boq_xlsx,
    export_filename,
    format_quantity,
    remarks,
)
from app.modules.sheets.boq_jobs import BoqJobManager, get_boq_jobs
from app.modules.sheets.boq_router import get_pdf_parser
from app.modules.sheets.boq_rows import (
    CATEGORY_PLAN,
    TOTAL_SERIALS,
    build_boq_rows,
    category_of,
    make_row,
    quantity_decimals,
    serial_sort_key,
)
from app.modules.sheets.boq_service import build_boq_result
from app.modules.sheets.llm_mapper import (
    _resolve_room_height_m,
    calculate_raw_materials_from_plan,
    generate_material_sheet,
    map_plan_to_materials,
)

EXTRACTED_PLAN = Path(__file__).resolve().parents[2] / "extracted_plan.json"
ROW_KEYS = {
    "serial_no",
    "item_code",
    "category",
    "sub_category",
    "name",
    "unit",
    "quantity",
    "components",
    "calc_type",
    "quote_status",
    "note",
}


@pytest.fixture
def plan() -> dict:
    return json.loads(EXTRACTED_PLAN.read_text(encoding="utf-8"))


@pytest.fixture
def result(plan) -> dict:
    return build_boq_result(plan, "Second Floor Plan.pdf")


def sample_rows() -> list[dict]:
    """Rows of every kind the contract allows, across several categories."""
    return [
        make_row(1, "aac_blocks", "AAC Blocks", "nos", 6143, note="Includes 5% waste."),
        make_row(2, "steel", "TMT Steel & Rebar <12 mm>", "t", 9.856),
        make_row(
            "17a",
            "paint",
            "Emulsion paint",
            "l",
            412.345,
            components=[
                {"label": "Wall area", "quantity": 828.46, "unit": "m2", "quantity_decimals": 2}
            ],
        ),
        make_row("17b", "primer", "Primer", "l", 80.5),
        make_row(
            30, "gate", "Main gate", "nos", 1, calc_type="allowance", note="Size to be confirmed"
        ),
        make_row(58, "site_office", "Site office", "nos", 0, quote_status="EXCLUDED_FROM_QUOTE"),
    ]


# ------------------------------------------------------------------------------ rows


def test_category_plan_places_all_59_serials_exactly_once():
    serials = [s for _, subs in CATEGORY_PLAN.values() for nums in subs.values() for s in nums]
    assert sorted(serials) == list(range(1, TOTAL_SERIALS + 1))
    assert list(CATEGORY_PLAN) == ["A", "B", "C", "D", "E", "F"]
    assert category_of(1) == ("A", "Structure and Masonry", "Masonry")
    assert category_of(19) == ("B", "Civil, Finishing and Waterproofing", "Painting")
    assert category_of(42) == ("D", "Electrical and HVAC", "Cabling and containment")
    assert category_of(57) == ("E", "Plumbing and Sanitary", "Drainage")
    assert category_of(59) == ("F", "Site Setup", "Preliminaries")
    with pytest.raises(KeyError):
        category_of(60)


def test_every_row_has_the_contract_fields(result):
    rows = result["items"]
    assert [r["serial_no"] for r in rows] == [1, 2, 3, 4, 5, 6, 7]
    for row in rows:
        assert ROW_KEYS <= set(row)
        assert row["category"] == "Structure and Masonry" and row["category_code"] == "A"
        assert row["calc_type"] == "geometry" and row["quote_status"] == "INCLUDED"
        assert isinstance(row["quantity"], (int, float)) and row["quantity"] > 0
        for part in row["components"]:
            assert set(part) == {"label", "quantity", "unit", "quantity_decimals"}
    assert [r["sub_category"] for r in rows] == [
        "Masonry",
        "Reinforcement",
        "Concrete and binders",
        "Aggregates",
        "Aggregates",
        "Wall finishes",
        "Flooring",
    ]


def test_rows_carry_the_calculator_quantities_and_keep_the_earlier_keys(result):
    by_key = result["materials_by_key"]
    for row in result["items"]:
        material = by_key[row["item_code"]]
        assert row["quantity"] == material["quantity"]
        assert row["name"] == material["name"]
        for kept in (
            "id",
            "surface_tag",
            "highlight_3d",
            "secondary_quantity",
            "secondary_unit",
            "details",
        ):
            assert row[kept] == material[kept]
    steel = next(r for r in result["items"] if r["item_code"] == "steel_rebar")
    assert (steel["unit"], steel["quantity_decimals"]) == ("t", 2)
    labels = {c["label"]: c for c in steel["components"]}
    assert labels["Steel weight"]["unit"] == "kg"
    assert (
        labels["12 m bars (12 mm average)"]["quantity"]
        == by_key["steel_rebar"]["secondary_quantity"]
    )


def test_the_calculator_keeps_every_key_it_returned_before(result):
    assert {
        "project_metadata",
        "geometry_summary",
        "materials",
        "materials_by_key",
        "level_summaries",
        "room_breakdown",
    } <= set(result)
    assert list(result["materials_by_key"]) == [
        "aac_blocks",
        "steel_rebar",
        "cement",
        "sand",
        "ballast_gitti",
        "plaster",
        "tiles",
    ]
    # the seven materials still carry their own (earlier) category and unit
    assert result["materials_by_key"]["aac_blocks"]["category"] == "Masonry & Wall Structure"
    assert result["materials_by_key"]["steel_rebar"]["unit"] == "metric_tons"
    assert calculate_raw_materials_from_plan is map_plan_to_materials
    assert generate_material_sheet is map_plan_to_materials


def test_result_summary_metadata_and_warnings(result):
    summary = result["geometry_summary"]
    assert summary["levels_count"] == 1
    assert summary["rooms_count"] == 21  # 23 spaces minus the lawn and the open shaft
    assert summary["bathrooms_count"] == 4
    assert summary["a_built_total_m2"] == 159.62
    meta = result["project_metadata"]
    assert meta["source_file_name"] == "Second Floor Plan.pdf"
    assert meta["building_type"] == "other"
    assert result["warnings"] == [
        "Level 1: the drawing states no ceiling height; 3.35 m was assumed."
    ]


def test_plan_warnings_reach_the_boq(plan):
    plan["warnings"] = ["Ground Floor: room 'HALL' is 900.00 m2. Check the drawing scale."]
    assert plan["warnings"][0] in build_boq_result(plan)["warnings"]


def test_same_plan_twice_gives_identical_output(plan):
    first = json.dumps(build_boq_result(plan, "a.pdf"), sort_keys=True)
    second = json.dumps(build_boq_result(json.loads(json.dumps(plan)), "a.pdf"), sort_keys=True)
    assert first == second


def test_room_and_level_breakdowns_keep_the_seven_core_materials(result):
    for scope in result["level_summaries"] + result["room_breakdown"]:
        assert len(scope["materials"]) == 7
        assert "items" not in scope


def test_an_open_kitchen_is_measured_as_a_room():
    plan = {
        "levels": [
            {
                "rooms": [
                    {
                        "id": "k",
                        "name": "Open Kitchen",
                        "polygon": [[0, 0], [4, 0], [4, 3], [0, 3]],
                    },
                    {"id": "o", "name": "OPEN TO SKY", "polygon": [[4, 0], [6, 0], [6, 3], [4, 3]]},
                ]
            }
        ]
    }
    rooms = {r["id"]: r for r in map_plan_to_materials(plan)["room_breakdown"]}
    assert rooms["k"]["kind"] == "indoor" and rooms["k"]["included_in_built_area"] is True
    assert rooms["o"]["kind"] == "void" and rooms["o"]["included_in_built_area"] is False
    assert map_plan_to_materials(plan)["geometry_summary"]["a_built_total_m2"] == 12.0


def test_stated_wall_height_is_used_and_default_becomes_the_standard_height():
    stated = {"wall_height": 2.8, "wall_height_source": "stated"}
    assert _resolve_room_height_m({}, stated) == 2.8
    assert _resolve_room_height_m({}, {"wall_height": 2.8, "wall_height_source": "default"}) == 3.35
    assert _resolve_room_height_m({}, {"wall_height": 2.8}) == 3.35  # older plans: unchanged
    assert _resolve_room_height_m({}, {"wall_height": 3.1}) == 3.1
    assert _resolve_room_height_m({"height_m": 4.0}, stated) == 4.0


def test_constants_live_in_one_module_and_are_unchanged():
    from app.modules.sheets import llm_mapper

    assert llm_mapper.SLAB_THICKNESS_M is constants.SLAB_THICKNESS_M
    assert (constants.SLAB_THICKNESS_M, constants.RCC_STRUCTURAL_MULTIPLIER) == (0.115, 1.35)
    assert (constants.DRY_VOLUME_MULTIPLIER, constants.M20_TOTAL_PARTS) == (1.54, 5.5)
    assert (constants.PLINTH_STEEL_KG_PER_M2, constants.FLOOR_STEEL_KG_PER_M2) == (34.0, 22.0)
    assert (constants.STEEL_WASTE_FACTOR, constants.TMT_12MM_ROD_WEIGHT_KG) == (1.10, 10.656)
    assert constants.CEMENT_BAGS_PER_M3 == 28.8


def test_serials_sort_naturally_with_lettered_rows():
    serials = [18, "17b", 2, "17a", 17, "10"]
    assert sorted(serials, key=serial_sort_key) == [2, "10", 17, "17a", "17b", 18]


def test_make_row_places_lettered_rows_and_rounds_by_unit():
    row = make_row("17a", "paint", "Paint", "l", 412.3456)
    assert (row["category_code"], row["sub_category"]) == ("B", "Painting")
    assert (row["quantity"], row["quantity_decimals"]) == (412.35, 2)
    count = make_row(1, "blocks", "Blocks", "nos", 6143.0)
    assert (count["quantity"], count["quantity_decimals"]) == (6143, 0)
    assert quantity_decimals("m2") == 2 and quantity_decimals("bags (50 kg)") == 0
    with pytest.raises(ValueError):
        make_row(1, "x", "X", "nos", 1, calc_type="guess")
    with pytest.raises(ValueError):
        make_row(1, "x", "X", "nos", 1, quote_status="MAYBE")


def test_build_boq_rows_skips_missing_materials():
    assert build_boq_rows({}) == []


# --------------------------------------------------------------------------- exports


def test_format_quantity_and_remarks():
    assert format_quantity(6143, 0) == "6,143"
    assert format_quantity(12345.678, 2) == "12,345.68"
    assert format_quantity(None, 2) == "0.00"
    rows = sample_rows()
    assert remarks(rows[0]) == "Includes 5% waste."
    assert remarks(rows[4]) == "Allowance. Size to be confirmed."
    assert remarks(rows[5]) == "Excluded from quote."
    assert remarks(rows[1]) == ""


def test_excel_export_rows_columns_and_formatting():
    rows = sample_rows()
    data = build_boq_xlsx(
        rows,
        ["Check the scale."],
        {"a_built_total_m2": 160.0, "levels_count": 1, "rooms_count": 12, "bathrooms_count": 3},
        {"project_title": "Test Villa", "source_file_name": "plan.pdf"},
        generated_on=date(2026, 11, 18),
    )
    wb = load_workbook(io.BytesIO(data))
    assert wb.sheetnames == ["BOQ", "Inputs and warnings"]
    ws = wb["BOQ"]
    assert [c.value for c in ws[1]] == list(COLUMNS)
    assert ws.max_row == 1 + len(rows)  # header + one row per item
    assert ws.max_column == len(COLUMNS) == 7
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref == f"A1:G{1 + len(rows)}"
    assert all(ws.column_dimensions[letter].width >= 8 for letter in "ABCDEFG")

    body = [[c.value for c in row] for row in ws.iter_rows(min_row=2)]
    assert [r[0] for r in body] == [1, 2, "17a", "17b", 30, 58]
    assert body[0] == [
        1,
        "A. Structure and Masonry",
        "Masonry",
        "AAC Blocks",
        "nos",
        6143,
        "Includes 5% waste.",
    ]
    quantities = [ws.cell(row=n, column=6) for n in range(2, ws.max_row + 1)]
    assert all(isinstance(c.value, (int, float)) for c in quantities)  # numeric cells, not text
    assert quantities[0].number_format == "#,##0" and quantities[1].number_format == "#,##0.00"
    assert body[1][5] == 9.86 and body[2][5] == 412.35
    assert body[4][6] == "Allowance. Size to be confirmed."
    assert body[5][6] == "Excluded from quote."

    info = [[c.value for c in row] for row in wb["Inputs and warnings"].iter_rows()]
    flat = {row[0]: row[1] for row in info if row and row[0]}
    assert flat["Project"] == "Test Villa" and flat["Source file"] == "plan.pdf"
    assert flat["Date"] == "2026-11-18" and flat["Built area (m2)"] == 160
    assert flat["Bathrooms"] == 3 and flat["Items"] == len(rows)
    assert ["Check the scale.", None] in info


def test_excel_export_of_a_real_result(result):
    wb = load_workbook(io.BytesIO(build_boq_xlsx(**_export_args(result))))
    assert wb["BOQ"].max_row == 1 + len(result["items"]) == 8


def _export_args(result: dict) -> dict:
    return {
        "items": result["items"],
        "warnings": result["warnings"],
        "geometry_summary": result["geometry_summary"],
        "project_metadata": result["project_metadata"],
    }


def test_pdf_export_generates_with_header_groups_footer_and_page_numbers():
    rows = sample_rows()
    data = build_boq_pdf(
        rows,
        ["Check the scale."],
        {"a_built_total_m2": 160.0, "a_built_total_sqft": 1722.2},
        {"project_title": "Test Villa", "source_file_name": "plan.pdf"},
        generated_on=date(2026, 11, 18),
    )
    assert data.startswith(b"%PDF")
    doc = pymupdf.open(stream=data, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    assert "Test Villa" in text and "plan.pdf" in text and "2026-11-18" in text
    assert "160.00 m2" in text and "1,722 sq ft" in text
    for group in (
        "A. Structure and Masonry",
        "B. Civil, Finishing and Waterproofing",
        "F. Site Setup",
    ):
        assert group in text
    assert "TMT Steel & Rebar <12 mm>" in text  # markup characters are escaped, not parsed
    assert "6,143" in text and "9.86" in text
    assert "Excluded from quote." in text and "Allowance. Size to be confirmed." in text
    assert "Check the scale." in text
    assert FOOTER_TEXT in text and f"Page 1 of {len(doc)}" in text


def test_pdf_export_paginates_a_full_bill():
    rows = [make_row(n, f"item_{n}", f"Material number {n}", "nos", n * 3) for n in range(1, 60)]
    doc = pymupdf.open(stream=build_boq_pdf(rows, [], {}, {}), filetype="pdf")
    assert len(doc) >= 2
    for number, page in enumerate(doc, start=1):
        text = page.get_text()
        assert FOOTER_TEXT in text and f"Page {number} of {len(doc)}" in text
        assert "Material" in text  # the column header repeats on every page
    assert "Bill of Quantities" in doc[0].get_text()  # default title when the plan has none


def test_pdf_export_with_no_rows_still_generates():
    assert build_boq_pdf([], [], {}, {}).startswith(b"%PDF")


def test_export_filename_is_safe():
    assert export_filename({"source_file_name": "SF.PLAN SMT. GEETA  ALT.NO-01.pdf"}, "xlsx") == (
        "BOQ_SF.PLAN_SMT._GEETA_ALT.NO-01.xlsx"
    )
    assert (
        export_filename({"source_file_name": '../../etc/"passwd".pdf'}, "pdf")
        == "BOQ_.._.._etc_passwd.pdf"
    )
    assert export_filename({}, "pdf") == "BOQ.pdf"


# ------------------------------------------------------------------------- endpoints


def minimal_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def boq_client(client, plan):
    """Authenticated client whose BOQ jobs use a fake parser and their own job manager."""
    from app.main import app

    state = {"parser": lambda pdf_bytes: plan}
    manager = BoqJobManager()
    app.dependency_overrides[get_pdf_parser] = lambda: lambda data: state["parser"](data)
    app.dependency_overrides[get_boq_jobs] = lambda: manager
    client.state_for_test = state
    return client


def wait_for_job(client, job_id: str) -> dict:
    for _ in range(200):
        state = client.get(f"/api/v1/sheets/boq/jobs/{job_id}").json()
        if state["status"] in ("done", "failed"):
            return state
        time.sleep(0.02)
    raise AssertionError("BOQ job did not finish")


def test_boq_upload_parse_calculate_and_result(boq_client):
    started = boq_client.post(
        "/api/v1/sheets/boq", files={"file": ("My Plan.pdf", minimal_pdf(), "application/pdf")}
    )
    assert started.status_code == 202
    job_id = started.json()["job_id"]

    state = wait_for_job(boq_client, job_id)
    assert state["status"] == "done" and state["progress"] == 100 and state["error"] is None
    assert [e["stage"] for e in state["events"]] == [
        "queued",
        "uploading",
        "parsing",
        "calculating",
        "done",
    ]
    assert [e["progress"] for e in state["events"]] == sorted(
        e["progress"] for e in state["events"]
    )

    result = boq_client.get(f"/api/v1/sheets/boq/jobs/{job_id}/result")
    assert result.status_code == 200
    body = result.json()
    assert {"items", "warnings", "geometry_summary", "project_metadata"} <= set(body)
    assert {"materials", "materials_by_key", "level_summaries", "room_breakdown"} <= set(body)
    assert len(body["items"]) == 7
    assert body["project_metadata"]["source_file_name"] == "My Plan.pdf"
    assert body["geometry_summary"]["bathrooms_count"] == 4


def test_boq_progress_is_streamed_as_sse(boq_client):
    job_id = boq_client.post(
        "/api/v1/sheets/boq", files={"file": ("p.pdf", minimal_pdf(), "application/pdf")}
    ).json()["job_id"]
    wait_for_job(boq_client, job_id)
    stream = boq_client.get(f"/api/v1/sheets/boq/jobs/{job_id}/events")
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    events = [
        json.loads(line[5:])
        for line in stream.text.splitlines()
        if line.startswith("data:") and line != "data: {}"
    ]
    assert [e["stage"] for e in events] == ["queued", "uploading", "parsing", "calculating", "done"]
    assert stream.text.rstrip().endswith("event: end\ndata: {}")


def test_boq_parser_failure_fails_the_job_with_the_typed_error(boq_client):
    def failing(_data: bytes) -> dict:
        raise PlanOutputInvalidError("The floor plan could not be read reliably from this drawing.")

    boq_client.state_for_test["parser"] = failing
    job_id = boq_client.post(
        "/api/v1/sheets/boq", files={"file": ("p.pdf", minimal_pdf(), "application/pdf")}
    ).json()["job_id"]
    state = wait_for_job(boq_client, job_id)
    assert state["status"] == "failed" and state["stage"] == "failed"
    assert state["error_code"] == "llm_output_invalid"
    assert "could not be read reliably" in state["error"]
    # no plan is substituted: there is no result, only the error
    result = boq_client.get(f"/api/v1/sheets/boq/jobs/{job_id}/result")
    assert result.status_code == 409 and "could not be read reliably" in result.json()["detail"]


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("plan.png", b"\x89PNG", "as a PDF"),
        ("plan.pdf", b"", "empty"),
    ],
)
def test_boq_upload_is_validated(boq_client, filename, content, message):
    response = boq_client.post(
        "/api/v1/sheets/boq", files={"file": (filename, content, "application/pdf")}
    )
    assert response.status_code == 400 and message in response.json()["detail"]


def test_boq_jobs_are_private_and_unknown_jobs_are_404(boq_client):
    from app.core.security import AuthenticatedUser, get_current_user
    from app.main import app

    job_id = boq_client.post(
        "/api/v1/sheets/boq", files={"file": ("p.pdf", minimal_pdf(), "application/pdf")}
    ).json()["job_id"]
    wait_for_job(boq_client, job_id)
    assert boq_client.get("/api/v1/sheets/boq/jobs/nope").status_code == 404

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        user_id="someone-else", email="other@example.com", metadata={}
    )
    for path in ("", "/events", "/result"):
        assert boq_client.get(f"/api/v1/sheets/boq/jobs/{job_id}{path}").status_code == 404


def test_boq_exports_are_built_from_the_posted_rows(boq_client, result):
    payload = {
        "items": result["items"],
        "warnings": result["warnings"],
        "geometry_summary": result["geometry_summary"],
        "project_metadata": result["project_metadata"],
    }
    pdf = boq_client.post("/api/v1/sheets/boq/export/pdf", json=payload)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-disposition"] == 'attachment; filename="BOQ_Second_Floor_Plan.pdf"'
    text = "\n".join(p.get_text() for p in pymupdf.open(stream=pdf.content, filetype="pdf"))
    assert "AAC Blocks" in text and "6,120" in text

    xlsx = boq_client.post("/api/v1/sheets/boq/export/xlsx", json=payload)
    assert xlsx.status_code == 200
    assert xlsx.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert (
        xlsx.headers["content-disposition"] == 'attachment; filename="BOQ_Second_Floor_Plan.xlsx"'
    )
    sheet = load_workbook(io.BytesIO(xlsx.content))["BOQ"]
    assert sheet.max_row == 8 and sheet.cell(row=2, column=6).value == 6120


def test_boq_export_rejects_a_malformed_payload(boq_client):
    bad = {"items": [{"serial_no": 1, "name": "X", "quote_status": "MAYBE"}]}
    assert boq_client.post("/api/v1/sheets/boq/export/pdf", json=bad).status_code == 422
