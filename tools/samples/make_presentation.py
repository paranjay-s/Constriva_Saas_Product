"""A2 samples: engineering and presentation sheets of the sample plans, side by side.

    uv --directory backend run python ../tools/samples/make_presentation.py OUT_DIR

For each sample plan (the feat/pro samples, backend/tests/floorplan/fixtures/golden): the
engineering and presentation PDF and PNG, and NAME_side_by_side.png (engineering left).
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("TESTING", "1")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import pymupdf  # noqa: E402

from app.modules.ai.floorplan.model.build import build_building  # noqa: E402
from app.modules.ai.floorplan.render.exports import export_plan  # noqa: E402
from tests.floorplan.snapshot_util import SAMPLES, sample_plan  # noqa: E402


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name in SAMPLES:
        plan = sample_plan(name)
        b = build_building(plan)
        pdfs = {}
        for view in ("engineering", "presentation"):
            pdf = export_plan(plan, "pdf", building=b, view=view).data
            (out / f"{name}_{view}.pdf").write_bytes(pdf)
            (out / f"{name}_{view}.png").write_bytes(
                export_plan(plan, "png", building=b, dpi=150, view=view).data
            )
            pdfs[view] = pdf
        doc = pymupdf.open()
        w, h = 420 * 2.835, 297 * 2.835
        page = doc.new_page(width=2 * w + 20, height=h + 40)
        for i, view in enumerate(("engineering", "presentation")):
            with pymupdf.open(stream=pdfs[view], filetype="pdf") as src:
                page.show_pdf_page(pymupdf.Rect(i * (w + 20), 30, i * (w + 20) + w, 30 + h), src, 0)
            page.insert_text((i * (w + 20) + 10, 20), view.upper(), fontsize=16)
        page.get_pixmap(dpi=90).save(str(out / f"{name}_side_by_side.png"))
        print(name, "ok", flush=True)


if __name__ == "__main__":
    main()
