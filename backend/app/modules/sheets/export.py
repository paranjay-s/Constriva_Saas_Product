"""
=============================================================================
Construtiva Bill of Materials (BOQ) Export Generator (CSV & PDF)
=============================================================================
File: app/modules/sheets/export.py
Purpose:
  Provides document export generation for construction cost estimates:
  - generate_sheet_csv: Generates RFC-4180 compliant CSV bytes for Excel / Sheets.
  - generate_sheet_pdf: Generates high-resolution printable PDF reports using ReportLab,
    featuring an architectural title header, formatted items table, and cost summary.
=============================================================================
"""

import io
import csv
import logging
from typing import Dict, Any
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logger = logging.getLogger("construtiva.sheets.export")


def generate_sheet_csv(sheet: Dict[str, Any], project_name: str = "Project") -> bytes:
    """
    Generates a structured, standard CSV export of a project's Bill of Materials (BOQ).

    Args:
        sheet (Dict[str, Any]): Cost sheet dictionary containing items, subtotal, and total_cost.
        project_name (str): Project display name.

    Returns:
        bytes: Raw UTF-8 encoded CSV bytes.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # 1. Header Information
    writer.writerow(["CONSTRUTIVA - BILL OF MATERIALS (BOQ) COST ESTIMATION"])
    writer.writerow(["Project Name:", project_name])
    writer.writerow(["Sheet Name:", sheet.get("name", "Cost Estimate")])
    writer.writerow(["Currency:", sheet.get("currency", "INR")])
    writer.writerow([])

    # 2. Table Column Headers
    writer.writerow([
        "Item #",
        "Material / Component",
        "Category",
        "Surface Tag",
        "Unit",
        "Base Qty",
        "Waste %",
        "Total Qty",
        "Rate (INR)",
        "Amount (INR)",
    ])

    # 3. Item Rows
    items = sheet.get("items", [])
    for idx, item in enumerate(items, start=1):
        waste_pct = f"{float(item.get('waste_factor', 0.0)) * 100:.1f}%"
        writer.writerow([
            idx,
            item.get("name", ""),
            item.get("category", ""),
            item.get("surface_tag", "-"),
            item.get("unit", ""),
            f"{float(item.get('quantity', 0.0)):.2f}",
            waste_pct,
            f"{float(item.get('total_quantity', 0.0)):.2f}",
            f"{float(item.get('unit_price', 0.0)):.2f}",
            f"{float(item.get('amount', 0.0)):.2f}",
        ])

    # 4. Summary Totals
    writer.writerow([])
    writer.writerow(["", "", "", "", "", "", "", "", "Subtotal:", f"{float(sheet.get('subtotal', 0.0)):.2f}"])
    contingency_rate_pct = f"{float(sheet.get('contingency_rate', 0.05)) * 100:.1f}%"
    writer.writerow(["", "", "", "", "", "", "", "", f"Site Contingency ({contingency_rate_pct}):", f"{float(sheet.get('contingency', 0.0)):.2f}"])
    writer.writerow(["", "", "", "", "", "", "", "", "TOTAL ESTIMATED COST (INR):", f"{float(sheet.get('total_cost', 0.0)):.2f}"])

    return output.getvalue().encode("utf-8")


def generate_sheet_pdf(sheet: Dict[str, Any], project_name: str = "Project") -> bytes:
    """
    Renders an architectural-grade PDF cost estimate report using ReportLab.

    Args:
        sheet (Dict[str, Any]): Cost sheet dictionary containing items, subtotal, and total_cost.
        project_name (str): Project display name.

    Returns:
        bytes: Raw binary PDF bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1E293B"),
    )
    meta_style = ParagraphStyle(
        "ReportMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748B"),
    )
    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )
    cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
    )

    story = []

    # Title & Subheader
    story.append(Paragraph(f"Construtiva - Bill of Materials (BOQ)", title_style))
    story.append(Paragraph(f"<b>Project:</b> {project_name} &nbsp;|&nbsp; <b>Estimate:</b> {sheet.get('name', 'Cost Estimate')} &nbsp;|&nbsp; <b>Currency:</b> INR", meta_style))
    story.append(Spacer(1, 14))

    # Table Data Construction
    table_data = [
        [
            Paragraph("<b>#</b>", cell_bold),
            Paragraph("<b>Material / Item</b>", cell_bold),
            Paragraph("<b>Category</b>", cell_bold),
            Paragraph("<b>Surface Tag</b>", cell_bold),
            Paragraph("<b>Unit</b>", cell_bold),
            Paragraph("<b>Base Qty</b>", cell_bold),
            Paragraph("<b>Waste</b>", cell_bold),
            Paragraph("<b>Total Qty</b>", cell_bold),
            Paragraph("<b>Rate (₹)</b>", cell_bold),
            Paragraph("<b>Amount (₹)</b>", cell_bold),
        ]
    ]

    items = sheet.get("items", [])
    for idx, item in enumerate(items, start=1):
        waste_str = f"{float(item.get('waste_factor', 0.0)) * 100:.0f}%"
        table_data.append([
            Paragraph(str(idx), cell_style),
            Paragraph(str(item.get("name", "")), cell_bold),
            Paragraph(str(item.get("category", "")), cell_style),
            Paragraph(str(item.get("surface_tag") or "-"), cell_style),
            Paragraph(str(item.get("unit", "")), cell_style),
            Paragraph(f"{float(item.get('quantity', 0.0)):,.2f}", cell_style),
            Paragraph(waste_str, cell_style),
            Paragraph(f"{float(item.get('total_quantity', 0.0)):,.2f}", cell_style),
            Paragraph(f"₹{float(item.get('unit_price', 0.0)):,.2f}", cell_style),
            Paragraph(f"₹{float(item.get('amount', 0.0)):,.2f}", cell_bold),
        ])

    col_widths = [25, 160, 110, 110, 45, 60, 45, 60, 65, 80]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    # Summary Totals Box
    subtotal = float(sheet.get("subtotal", 0.0))
    contingency = float(sheet.get("contingency", 0.0))
    total_cost = float(sheet.get("total_cost", 0.0))

    summary_data = [
        [Paragraph("<b>Subtotal:</b>", cell_style), Paragraph(f"₹{subtotal:,.2f}", cell_style)],
        [Paragraph("<b>Site Contingency (5%):</b>", cell_style), Paragraph(f"₹{contingency:,.2f}", cell_style)],
        [Paragraph("<b>TOTAL ESTIMATED COST:</b>", cell_bold), Paragraph(f"<b>₹{total_cost:,.2f}</b>", cell_bold)],
    ]
    summary_table = Table(summary_data, colWidths=[160, 100], hAlign="RIGHT")
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#E2E8F0")),
    ]))
    story.append(summary_table)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
