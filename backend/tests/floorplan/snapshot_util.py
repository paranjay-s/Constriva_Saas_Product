"""Engineering export snapshots: bytes with only the run-dependent stamps blanked.

A PDF carries its creation and modification dates (document and embedded file) and a
random file /ID; a DXF carries two random GUIDs and creation stamps. Everything else must
be byte for byte the same as on feat/pro (tests/floorplan/fixtures/golden).
"""

import hashlib
import json
import re
from pathlib import Path

from app.modules.ai.floorplan.model.build import build_building
from app.modules.ai.floorplan.render.exports import export_plan
from app.modules.ai.floorplan.schemas.plan import FloorPlan

GOLDEN = Path(__file__).parent / "fixtures" / "golden"
SAMPLES = ("villa-1500", "villa-3000", "villa-5000", "villa-8000", "nandu")
FORMATS = ("pdf", "svg", "png", "dxf")

_PDF_DATE = re.compile(rb"D:\d{14}[^)]{0,12}")
_PDF_STR = rb"(?:<[0-9A-Fa-f]*>|\((?:\\.|[^\\)])*\))"  # hex or literal string
_PDF_ID = re.compile(rb"/ID\s*\[" + _PDF_STR + rb"\s*" + _PDF_STR + rb"\]", re.DOTALL)
_DXF_GUID = re.compile(rb"\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}")
_DXF_STAMP = re.compile(rb"(\d+\.\d+\.\d+ @ )\d{4}-\d\d-\d\dT[0-9:.+]+")
_DXF_TD = re.compile(rb"(\$TD[A-Z]+\r?\n\s*40\r?\n)[0-9.]+")


def _dxf_drawing(data: bytes) -> bytes:
    """What a DXF draws, without its bookkeeping: ezdxf numbers its objects in an order that depends
    on which of its modules a process imported first, so handles (and every reference to them) can
    differ between two runs of the same code. Each layout's and block's entities are listed with
    their type and attributes (handles and owners left out), plus the layers and text styles."""
    import io

    import ezdxf

    doc = ezdxf.read(io.StringIO(data.decode("utf-8", errors="replace")))
    skip = {"handle", "owner", "reactors", "extension_dict"}
    out = []

    def attrs(e):
        d = {k: v for k, v in e.dxfattribs().items() if k not in skip}
        return repr(sorted((k, repr(v)) for k, v in d.items()))

    for layout in doc.layouts:
        out += [f"L {layout.name} {e.dxftype()} {attrs(e)}" for e in layout]
    for blk in doc.blocks:
        out += [f"B {blk.name} {e.dxftype()} {attrs(e)}" for e in blk]
    out += [f"Y {lay.dxf.name} {attrs(lay)}" for lay in doc.layers]
    out += [f"S {st.dxf.name} {attrs(st)}" for st in doc.styles]
    return "\n".join(out).encode("utf-8")


def normalise(data: bytes, fmt: str) -> bytes:
    if fmt == "pdf":
        return _PDF_ID.sub(b"/ID[]", _PDF_DATE.sub(b"D:0", data))
    if fmt == "dxf":
        data = _DXF_GUID.sub(b"{GUID}", data)
        data = _DXF_STAMP.sub(rb"\1STAMP", data)
        return _dxf_drawing(data)
    return data


def sample_plan(name: str) -> FloorPlan:
    path = GOLDEN / f"sample_{name}.plan.json"
    return FloorPlan.model_validate(json.loads(path.read_text()))


def engineering_hash(name: str, fmt: str) -> str:
    plan = sample_plan(name)
    data = export_plan(plan, fmt, building=build_building(plan), dpi=100).data
    return hashlib.sha256(normalise(data, fmt)).hexdigest()
