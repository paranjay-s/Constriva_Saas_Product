"""BOQ exports. The PDF and the Excel file are both built from the same BOQ rows.

Columns of both: S.No, Category, Sub-category, Material, Unit, Quantity, Remarks.
Remarks says when an item is excluded from the quote or is an allowance, then its note.

Nothing here is specific to one building: every figure printed comes from the rows and
the summary passed in.
"""

import io
import re
from datetime import date
from typing import Any
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.sheets.boq_rows import quantity_decimals, serial_sort_key

COLUMNS = ("S.No", "Category", "Sub-category", "Material", "Unit", "Quantity", "Remarks")
FOOTER_TEXT = "Estimated quantities from a 2D plan. Verify before procurement."
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MIME = "application/pdf"

EXCLUDED_REMARK = "Excluded from quote"
ALLOWANCE_REMARK = "Allowance"


def _rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda r: serial_sort_key(r.get("serial_no")))


def _decimals(row: dict[str, Any]) -> int:
    given = row.get("quantity_decimals")
    return given if isinstance(given, int) else quantity_decimals(row.get("unit", ""))


def format_quantity(value: Any, decimals: int) -> str:
    """Thousands separators; whole numbers for counts, fixed decimals for measures."""
    return f"{float(value or 0.0):,.{decimals}f}"


def remarks(row: dict[str, Any]) -> str:
    parts = []
    if row.get("quote_status") == "EXCLUDED_FROM_QUOTE":
        parts.append(EXCLUDED_REMARK)
    if row.get("calc_type") == "allowance":
        parts.append(ALLOWANCE_REMARK)
    note = str(row.get("note") or "").strip()
    if note:
        parts.append(note)
    return ". ".join(p.rstrip(".") for p in parts) + ("." if parts else "")


def _category_label(row: dict[str, Any]) -> str:
    code = str(row.get("category_code") or "").strip()
    name = str(row.get("category") or "").strip()
    return f"{code}. {name}" if code else name


def _title(metadata: dict[str, Any]) -> str:
    title = str(metadata.get("project_title") or "").strip()
    return title if title and title.upper() != "NA" else "Bill of Quantities"


def _built_area(summary: dict[str, Any]) -> str:
    area = summary.get("a_built_total_m2")
    if not isinstance(area, (int, float)):
        return "-"
    sqft = summary.get("a_built_total_sqft")
    extra = f" ({sqft:,.0f} sq ft)" if isinstance(sqft, (int, float)) else ""
    return f"{area:,.2f} m2{extra}"


def export_filename(metadata: dict[str, Any], extension: str) -> str:
    source = str(metadata.get("source_file_name") or "").rsplit(".", 1)[0]
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", source).strip("_")[:60]
    return f"BOQ_{safe}.{extension}" if safe else f"BOQ.{extension}"


# ----------------------------------------------------------------------------- Excel


def build_boq_xlsx(
    items: list[dict[str, Any]],
    warnings: list[str] | None = None,
    geometry_summary: dict[str, Any] | None = None,
    project_metadata: dict[str, Any] | None = None,
    generated_on: date | None = None,
) -> bytes:
    """Sheet "BOQ": one row per item. Sheet "Inputs and warnings": what it was built from."""
    summary = geometry_summary or {}
    metadata = project_metadata or {}
    wb = Workbook()

    ws = wb.active
    ws.title = "BOQ"
    ws.append(list(COLUMNS))
    header_fill = PatternFill("solid", fgColor="1F2937")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")
    for row in _rows(items):
        serial = row.get("serial_no")
        decimals = _decimals(row)
        quantity = float(row.get("quantity") or 0.0)
        ws.append(
            [
                serial if isinstance(serial, int) else str(serial),
                _category_label(row),
                row.get("sub_category", ""),
                row.get("name", ""),
                row.get("unit", ""),
                round(quantity, decimals) if decimals else int(round(quantity)),
                remarks(row),
            ]
        )
        quantity_cell = ws.cell(row=ws.max_row, column=6)
        quantity_cell.number_format = "#,##0.00" if decimals else "#,##0"
        quantity_cell.alignment = Alignment(horizontal="right")
        ws.cell(row=ws.max_row, column=7).alignment = Alignment(wrap_text=True, vertical="top")
        if row.get("quote_status") == "EXCLUDED_FROM_QUOTE":
            for cell in ws[ws.max_row]:
                cell.font = Font(italic=True, color="6B7280")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{ws.max_row}"
    for index, width in enumerate((8, 34, 26, 52, 14, 14, 60), start=1):
        ws.column_dimensions[get_column_letter(index)].width = width

    info = wb.create_sheet("Inputs and warnings")
    info.append(["Input", "Value"])
    for cell in info[1]:
        cell.font = Font(bold=True)
    facts: list[tuple[str, Any]] = [
        ("Project", _title(metadata)),
        ("Source file", metadata.get("source_file_name") or "-"),
        ("Date", (generated_on or date.today()).isoformat()),
        ("Client", metadata.get("client") or "-"),
        ("Building type", metadata.get("building_type") or "-"),
        ("Scale source", metadata.get("scale_source") or "-"),
        ("Items", len(items)),
    ]
    for label, key in (
        ("Built area (m2)", "a_built_total_m2"),
        ("Built area (sq ft)", "a_built_total_sqft"),
        ("Ground floor area (m2)", "a_ground_m2"),
        ("Levels", "levels_count"),
        ("Rooms", "rooms_count"),
        ("Bathrooms", "bathrooms_count"),
        ("Doors", "total_doors"),
        ("Windows", "total_windows"),
        ("Columns", "total_columns"),
        ("Net wall area (m2)", "a_net_wall_m2"),
        ("Plinth wall area (m2)", "a_plinth_wall_m2"),
        ("Parapet wall area (m2)", "a_parapet_wall_m2"),
        ("Total masonry area (m2)", "a_total_masonry_m2"),
        ("Wet concrete (m3)", "v_wet_concrete_m3"),
    ):
        if key in summary:
            facts.append((label, summary[key]))
    for label, value in facts:
        info.append([label, value])
    info.append([])
    info.append(["Warnings"])
    info.cell(row=info.max_row, column=1).font = Font(bold=True)
    for warning in warnings or ["None"]:
        info.append([warning])
        info.cell(row=info.max_row, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    info.append([])
    info.append([FOOTER_TEXT])
    info.column_dimensions["A"].width = 60
    info.column_dimensions["B"].width = 40

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ------------------------------------------------------------------------------- PDF


class _NumberedCanvas(pdf_canvas.Canvas):
    """Draws the footer and "Page X of Y" once the page count is known."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_pages: list[dict[str, Any]] = []

    def showPage(self) -> None:  # noqa: N802 (reportlab API name)
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            width, _ = self._pagesize
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawString(36, 22, FOOTER_TEXT)
            self.drawRightString(width - 36, 22, f"Page {self._pageNumber} of {total}")
            super().showPage()
        super().save()


def build_boq_pdf(
    items: list[dict[str, Any]],
    warnings: list[str] | None = None,
    geometry_summary: dict[str, Any] | None = None,
    project_metadata: dict[str, Any] | None = None,
    generated_on: date | None = None,
) -> bytes:
    """Header (title, source file, date, built area), rows grouped by category, footer."""
    summary = geometry_summary or {}
    metadata = project_metadata or {}
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BoqTitle", parent=styles["Heading1"], fontSize=17, leading=21, spaceAfter=4
    )
    meta_style = ParagraphStyle(
        "BoqMeta",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569"),
    )
    cell = ParagraphStyle("BoqCell", parent=styles["Normal"], fontSize=8, leading=10)
    cell_muted = ParagraphStyle("BoqCellMuted", parent=cell, textColor=colors.HexColor("#6B7280"))
    cell_right = ParagraphStyle("BoqCellRight", parent=cell, alignment=2)
    cell_right_muted = ParagraphStyle("BoqCellRightMuted", parent=cell_muted, alignment=2)
    head = ParagraphStyle("BoqHead", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)
    group = ParagraphStyle("BoqGroup", parent=cell, fontName="Helvetica-Bold", fontSize=9)

    def p(text: Any, style: ParagraphStyle) -> Paragraph:
        return Paragraph(escape(str(text if text is not None else "")), style)

    story: list[Any] = [
        p(_title(metadata), title_style),
        p(
            f"Source file: {metadata.get('source_file_name') or '-'}   |   "
            f"Date: {(generated_on or date.today()).isoformat()}   |   "
            f"Built area: {_built_area(summary)}   |   Items: {len(items)}",
            meta_style,
        ),
        Spacer(1, 10),
    ]

    data: list[list[Any]] = [[p(c, head) for c in COLUMNS]]
    style_cmds: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    current_category = None
    for row in _rows(items):
        label = _category_label(row)
        if label != current_category:
            current_category = label
            data.append([p(label, group)] + [""] * (len(COLUMNS) - 1))
            line = len(data) - 1
            style_cmds += [
                ("SPAN", (0, line), (-1, line)),
                ("BACKGROUND", (0, line), (-1, line), colors.HexColor("#E2E8F0")),
            ]
        excluded = row.get("quote_status") == "EXCLUDED_FROM_QUOTE"
        text_style = cell_muted if excluded else cell
        number_style = cell_right_muted if excluded else cell_right
        data.append(
            [
                p(row.get("serial_no", ""), text_style),
                p(row.get("category", ""), text_style),
                p(row.get("sub_category", ""), text_style),
                p(row.get("name", ""), text_style),
                p(row.get("unit", ""), text_style),
                p(format_quantity(row.get("quantity"), _decimals(row)), number_style),
                p(remarks(row), text_style),
            ]
        )
        if excluded:
            line = len(data) - 1
            style_cmds.append(("BACKGROUND", (0, line), (-1, line), colors.HexColor("#F8FAFC")))
    if len(data) == 1:
        data.append([p("No items.", cell)] + [""] * (len(COLUMNS) - 1))
        style_cmds.append(("SPAN", (0, 1), (-1, 1)))

    table = Table(data, colWidths=[34, 112, 104, 214, 62, 70, 174], repeatRows=1)
    table.setStyle(TableStyle(style_cmds))
    story.append(table)

    if warnings:
        story += [Spacer(1, 12), p("Warnings", group)]
        story += [p(f"- {warning}", cell) for warning in warnings]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=36,
        rightMargin=36,
        topMargin=32,
        bottomMargin=40,
        title=_title(metadata),
    )
    doc.build(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()
