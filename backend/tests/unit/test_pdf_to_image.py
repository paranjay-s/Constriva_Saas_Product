"""
=============================================================================
Construtiva PDF to PNG Rasterizer Unit Tests
=============================================================================
File: tests/unit/test_pdf_to_image.py
Purpose:
  Tests high-resolution 300 DPI PNG extraction from PDF architectural drawings.
=============================================================================
"""

import pytest
try:
    import pymupdf as fitz
except ImportError:
    import fitz
from app.modules.parsing.pdf_to_image import convert_pdf_page_to_png


def create_dummy_pdf() -> bytes:
    """Helper to generate a clean 1-page vector PDF in memory."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    # Draw sample architectural wall line and text
    page.draw_rect(fitz.Rect(50, 50, 550, 750), color=(0, 0, 0), width=2)
    page.insert_text(fitz.Point(100, 100), "MASTER BEDROOM 14x12", fontsize=16)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_convert_pdf_page_to_png_success():
    """Verifies that a valid PDF is rasterized to PNG with correct dimensions and headers."""
    pdf_bytes = create_dummy_pdf()
    png_bytes, width, height = convert_pdf_page_to_png(pdf_bytes, page_number=0, dpi=300)

    # 1. Check PNG signature bytes (\x89PNG\r\n\x1a\n)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    
    # 2. Check 300 DPI scaled dimensions (600 * 300 / 72 = 2500 px width)
    expected_w = int(600 * 300 / 72)
    expected_h = int(800 * 300 / 72)
    assert abs(width - expected_w) <= 2
    assert abs(height - expected_h) <= 2
    assert len(png_bytes) > 1000


def test_convert_pdf_empty_bytes_raises():
    """Verifies ValueError is raised when empty bytes are passed."""
    with pytest.raises(ValueError, match="Cannot rasterize empty PDF bytes"):
        convert_pdf_page_to_png(b"")


def test_convert_pdf_page_out_of_bounds_raises():
    """Verifies ValueError is raised when page index exceeds total pages."""
    pdf_bytes = create_dummy_pdf()
    with pytest.raises(ValueError, match="exceeds document page count"):
        convert_pdf_page_to_png(pdf_bytes, page_number=99)


