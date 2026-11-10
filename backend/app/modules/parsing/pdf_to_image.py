"""
=============================================================================
Construtiva High-Resolution PDF Rasterizer Module
=============================================================================
File: app/modules/parsing/pdf_to_image.py
Purpose:
  Converts 2D architectural floor plan PDF blueprints into high-resolution
  PNG images (300 DPI) using PyMuPDF (fitz).
  
  The generated image preserves crisp wall centerlines, door swings, dimension
  labels, and room annotations needed for accurate LLM vision parsing and
  3D coordinate extraction.
=============================================================================
"""

import io
import logging
from typing import Tuple
import fitz  # PyMuPDF

logger = logging.getLogger("construtiva.rasterizer")


def convert_pdf_page_to_png(
    pdf_bytes: bytes,
    page_number: int = 0,
    dpi: int = 300
) -> Tuple[bytes, int, int]:
    """
    Renders a specific page of an architectural PDF into a crisp, high-resolution PNG image.

    Args:
        pdf_bytes (bytes): Raw binary content of the uploaded PDF floor plan.
        page_number (int): Zero-based page index to render (defaults to 0 for single-sheet blueprints).
        dpi (int): Output rendering resolution in dots per inch (default 300 DPI for high architectural fidelity).

    Returns:
        Tuple[bytes, int, int]:
            - bytes: Raw PNG image bytes ready for Supabase Storage upload or vision analysis.
            - int: Image pixel width.
            - int: Image pixel height.

    Raises:
        ValueError: If PDF bytes are corrupt, empty, or page_number is out of bounds.
    """
    if not pdf_bytes:
        raise ValueError("Cannot rasterize empty PDF bytes.")

    try:
        # Open PDF document from memory
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        if page_number >= len(doc):
            raise ValueError(
                f"Requested page {page_number + 1} exceeds document page count of {len(doc)}."
            )

        page = doc.load_page(page_number)

        # Standard PDF resolution is 72 points per inch.
        # Scale matrix = dpi / 72 (e.g. 300 / 72 = 4.1666x scaling)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        # Render page to a high-fidelity RGB pixmap
        # alpha=False renders on clean solid white background for optimal OCR and edge detection
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        width = pixmap.width
        height = pixmap.height

        # Convert pixmap into PNG byte stream
        png_bytes = pixmap.tobytes("png")

        doc.close()

        logger.info(
            f"Successfully rendered PDF page {page_number + 1} to {width}x{height} PNG at {dpi} DPI."
        )
        return png_bytes, width, height

    except Exception as e:
        logger.error(f"Failed to rasterize PDF page: {e}")
        raise ValueError(f"PDF rasterization failed: {str(e)}") from e
