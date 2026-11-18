"""Turn a plan PDF into the provider-neutral input the parser sends to an LLM.

Every model gets the same two things, whatever the provider:

  * each page rendered to PNG at a fixed DPI (sheets too large for that are scaled down by
    a rule that depends only on the page size, so the same PDF always renders the same);
  * the text PyMuPDF can read from the page (room labels, dimensions, title block), one
    block per line in reading order.

Scanned PDFs have no text layer; they simply produce an empty text section.
"""

import hashlib
import logging
from dataclasses import dataclass, field

try:
    import pymupdf as fitz
except ImportError:  # older PyMuPDF
    import fitz

from app.modules.parsing.errors import (
    FileTooLargeError,
    NotAPdfError,
    PdfInputError,
    TooManyPagesError,
)

logger = logging.getLogger("construtiva.parsing.pdf_input")

RENDER_DPI = 300  # the DPI the blueprint import has always used
MAX_IMAGE_SIDE_PX = 5000  # an A3 sheet at 300 DPI is 4961 px on its long side
MAX_TEXT_CHARS_PER_PAGE = 6000
MAX_TEXT_BLOCKS_PER_PAGE = 400


@dataclass(frozen=True)
class PlanPage:
    number: int  # 1-based
    png: bytes
    width_px: int
    height_px: int
    dpi: int
    text: str


@dataclass(frozen=True)
class PlanPdfInput:
    sha256: str
    page_count: int
    pages: list[PlanPage] = field(default_factory=list)


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def effective_dpi(width_pt: float, height_pt: float) -> int:
    """RENDER_DPI, lowered just enough that the long side fits MAX_IMAGE_SIDE_PX."""
    long_side_px = max(width_pt, height_pt) / 72.0 * RENDER_DPI
    if long_side_px <= MAX_IMAGE_SIDE_PX:
        return RENDER_DPI
    return max(72, int(RENDER_DPI * MAX_IMAGE_SIDE_PX / long_side_px))


def _page_text(page: "fitz.Page") -> str:
    """The page's text blocks, one per line, in reading order (top to bottom, left to right).

    Reading order follows the page as rendered, so the page's own rotation is applied
    before sorting. Positions are not passed on: a model that sees page coordinates next
    to every label tends to answer in page coordinates instead of metres.
    """
    width, height = page.rect.width, page.rect.height
    if width <= 0 or height <= 0:
        return ""
    rows: list[tuple[float, float, str]] = []
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, raw = block[:5]
        if len(block) > 6 and block[6] != 0:  # image block
            continue
        label = " ".join(str(raw).split())
        if not label:
            continue
        centre = fitz.Point((x0 + x1) / 2.0, (y0 + y1) / 2.0) * page.rotation_matrix
        rows.append((round(centre.y / height, 2), round(centre.x / width, 2), label))
    rows.sort()
    lines: list[str] = []
    used = 0
    for _, _, label in rows[:MAX_TEXT_BLOCKS_PER_PAGE]:
        if used + len(label) > MAX_TEXT_CHARS_PER_PAGE:
            break
        lines.append(label)
        used += len(label) + 1
    return "\n".join(lines)


def _open(pdf_bytes: bytes) -> "fitz.Document":
    if not pdf_bytes:
        raise PdfInputError("The uploaded file is empty.")
    if b"%PDF-" not in pdf_bytes[:1024]:
        raise NotAPdfError("This file is not a PDF. Please upload the floor plan as a PDF.")
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise PdfInputError("This file could not be opened as a PDF.") from e
    if doc.needs_pass:
        doc.close()
        raise PdfInputError("The PDF is password protected.")
    if len(doc) == 0:
        doc.close()
        raise PdfInputError("The PDF has no pages.")
    return doc


def check_plan_pdf(
    pdf_bytes: bytes,
    filename: str | None = None,
    *,
    max_bytes: int | None = None,
    max_pages: int | None = None,
) -> int:
    """Turn away an upload that must not reach a model. Returns the page count.

    Checks, in order: the file name ends in .pdf (when a name is given), the size is
    within `max_bytes`, the content is a PDF that opens, and it has at most `max_pages`
    pages. The limits default to PLAN_PARSER_MAX_PDF_MB and PLAN_PARSER_MAX_PDF_PAGES.
    Raises a PlanParseError subclass with a message for the user.
    """
    from app.modules.parsing.settings import get_settings

    settings = get_settings()
    max_bytes = settings.max_pdf_bytes if max_bytes is None else max_bytes
    max_pages = settings.max_pdf_pages if max_pages is None else max_pages

    if filename is not None and not filename.lower().endswith(".pdf"):
        raise NotAPdfError("Please upload the floor plan as a PDF file.")
    if len(pdf_bytes) > max_bytes:
        raise FileTooLargeError(
            f"This PDF is {len(pdf_bytes) / 1048576:.1f} MB. "
            f"The largest file accepted is {max_bytes / 1048576:g} MB."
        )
    doc = _open(pdf_bytes)
    try:
        page_count = len(doc)
    finally:
        doc.close()
    if page_count > max_pages:
        raise TooManyPagesError(
            f"This PDF has {page_count} pages. A plan may have at most {max_pages} pages. "
            "Upload only the pages that show the floor plans."
        )
    return page_count


def load_plan_pdf(
    pdf_bytes: bytes, max_pages: int | None = None, max_bytes: int | None = None
) -> PlanPdfInput:
    """Render every page and read its text.

    The upload limits are checked first (`check_plan_pdf`), so an oversized PDF is
    rejected here even when a caller did not check it. Raises a PlanParseError subclass.
    """
    page_count = check_plan_pdf(pdf_bytes, max_bytes=max_bytes, max_pages=max_pages)
    doc = _open(pdf_bytes)
    try:
        pages: list[PlanPage] = []
        blank_pages = 0
        for index in range(page_count):
            page = doc.load_page(index)
            dpi = effective_dpi(page.rect.width, page.rect.height)
            zoom = dpi / 72.0
            try:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                png = pixmap.tobytes("png")
            except Exception as e:
                raise PdfInputError(f"Page {index + 1} of the PDF could not be rendered.") from e
            if pixmap.is_unicolor:
                blank_pages += 1
            pages.append(
                PlanPage(
                    number=index + 1,
                    png=png,
                    width_px=pixmap.width,
                    height_px=pixmap.height,
                    dpi=dpi,
                    text=_page_text(page),
                )
            )
        if blank_pages == len(pages):
            raise PdfInputError("The PDF pages are blank. Upload a drawing of the floor plan.")
    finally:
        doc.close()
    logger.info(
        "plan pdf: %d page(s), %s",
        page_count,
        ", ".join(f"p{p.number} {p.width_px}x{p.height_px}@{p.dpi}dpi" for p in pages),
    )
    return PlanPdfInput(sha256=sha256_of(pdf_bytes), page_count=page_count, pages=pages)
