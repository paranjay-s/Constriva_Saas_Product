"""CAD and BIM exports: DXF (ezdxf audit, FreeCAD), IFC (validation, FreeCAD), DWG
(read back), and the signed building model inside the PDF (3D and BOQ use it)."""

import io
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import ezdxf
import ifcopenshell
import ifcopenshell.validate
import pymupdf
import pytest
from pydantic import SecretStr

from app.modules.ai.floorplan.model.build import build_building
from app.modules.ai.floorplan.model.embed import (
    embed_model,
    read_embedded_model,
)
from app.modules.ai.floorplan.render.cad_dxf import LAYERS, building_dxf
from app.modules.ai.floorplan.render.cad_ifc import building_ifc
from app.modules.ai.floorplan.render.dwg import converter_path, dwg_to_dxf, dxf_to_dwg
from app.modules.ai.floorplan.render.exports import export_plan, read_plan_reference
from app.modules.ai.floorplan.settings import get_settings
from tests.floorplan.test_fp_building import _pool_plan

FREECAD = "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
KEY = b"test-key"


@pytest.fixture(scope="module")
def building():
    plan = _pool_plan()
    plan = plan.model_copy(update={"id": "11111111-2222-3333-4444-555555555555"})
    return build_building(plan, date="2026-11-20")


@pytest.fixture(scope="module")
def dxf(building) -> bytes:
    return building_dxf(building)


def _doc(data: bytes):
    return ezdxf.read(io.StringIO(data.decode("utf-8")))


def test_dxf_passes_the_audit_in_millimetres(dxf) -> None:
    doc = _doc(dxf)
    auditor = doc.audit()
    assert not auditor.has_errors, [str(e) for e in auditor.errors][:3]
    assert doc.units == ezdxf.units.MM


def test_dxf_layers_blocks_dimensions_and_hatches(dxf, building) -> None:
    doc = _doc(dxf)
    assert set(LAYERS) <= {layer.dxf.name for layer in doc.layers}
    kinds = Counter(e.dxftype() for e in doc.modelspace())
    assert kinds["DIMENSION"] >= 8 and kinds["HATCH"] >= 3 and kinds["INSERT"] >= 5
    blocks = {b.name for b in doc.blocks}
    assert any(n.startswith("DOOR_HINGED_") for n in blocks)
    assert any(n.startswith("WINDOW_") for n in blocks)
    assert any(n.startswith("WC_") or n.startswith("BED_") for n in blocks)
    # the dimension entities measure the real geometry (mm)
    width = building.site.width
    measures = [round(d.get_measurement()) for d in doc.modelspace().query("DIMENSION")]
    assert width in measures
    assert "A3" in [lay.name for lay in doc.layouts]


def test_ifc_is_valid_and_has_every_element(building) -> None:
    data = building_ifc(building)
    with tempfile.NamedTemporaryFile(suffix=".ifc") as tmp:
        tmp.write(data)
        tmp.flush()
        f = ifcopenshell.open(tmp.name)
    log = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(f, log, express_rules=True)
    assert log.statements == []
    st = building.storeys[0]
    assert len(f.by_type("IfcWall")) == len(st.walls)
    doors = [o for o in st.openings if o.kind == "door"]
    assert len(f.by_type("IfcDoor")) == len(doors)
    assert len(f.by_type("IfcWindow")) == len(st.openings) - len(doors)
    assert len(f.by_type("IfcSpace")) == len(st.rooms)
    assert len(f.by_type("IfcSlab")) == 1 and len(f.by_type("IfcBuildingStorey")) == 1
    assert len(f.by_type("IfcRelVoidsElement")) == len(st.openings)
    assert len(f.by_type("IfcRelFillsElement")) == len(st.openings)


@pytest.mark.skipif(converter_path() is None, reason="ODA File Converter not installed")
def test_dwg_reads_back_with_the_same_entities(dxf) -> None:
    dwg = dxf_to_dwg(dxf)
    assert dwg[:4] == b"AC10"  # a DWG header
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "back.dxf"
        path.write_bytes(dwg_to_dxf(dwg))
        back = ezdxf.readfile(path)
    src = _doc(dxf)
    assert Counter(e.dxftype() for e in back.modelspace()) == Counter(
        e.dxftype() for e in src.modelspace()
    )
    assert {la.dxf.name for la in src.layers} <= {la.dxf.name for la in back.layers}


def _freecad(script: str, path: Path) -> str:
    code = f"import sys; sys.argv=['x', {str(path)!r}]\n" + script
    out = subprocess.run(
        [FREECAD, "-c", code], capture_output=True, text=True, timeout=240, check=False
    )
    return out.stdout + out.stderr


@pytest.mark.skipif(not Path(FREECAD).exists(), reason="FreeCAD not installed")
def test_freecad_opens_the_dxf_and_the_ifc(dxf, building, tmp_path) -> None:
    (tmp_path / "plan.dxf").write_bytes(dxf)
    out = _freecad(
        "import FreeCAD, importDXF\n"
        "d = FreeCAD.newDocument('c'); importDXF.insert(sys.argv[-1], d.Name)\n"
        "print('OBJECTS', len(d.Objects))\n",
        tmp_path / "plan.dxf",
    )
    n = int(out.split("OBJECTS", 1)[1].split()[0])
    assert n > 20, out[-500:]
    (tmp_path / "plan.ifc").write_bytes(building_ifc(building))
    out = _freecad(
        "import FreeCAD\nfrom nativeifc import ifc_import\n"
        "d = FreeCAD.newDocument('i'); ifc_import.insert(sys.argv[-1], d.Name, strategy=2,"
        " shapemode=0, switchwb=False, silent=True)\n"
        "print('CLASSES', sorted({str(getattr(o, 'Class', '')) for o in d.Objects}))\n",
        tmp_path / "plan.ifc",
    )
    for cls in ("IfcWall", "IfcDoor", "IfcSpace", "IfcSlab"):
        assert cls in out, out[-800:]


def test_pdf_carries_the_plan_id_and_the_signed_model(building, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "model_signing_key", SecretStr(KEY.decode()))
    plan = _pool_plan().model_copy(update={"id": building.meta.plan_id})
    pdf = export_plan(plan, "pdf", version=3, building=building).data
    assert read_plan_reference(pdf).plan_id == building.meta.plan_id
    found = read_embedded_model(pdf)
    assert found is not None and found.signed and found.building == building
    # tampering with the model breaks the signature
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        data = doc.embfile_get("building.json").replace(b'"living_1"', b'"living_9"', 1)
        doc.embfile_del("building.json")
        doc.embfile_add("building.json", data, filename="building.json")
        tampered = doc.tobytes()
    bad = read_embedded_model(tampered)
    assert bad is None or not bad.signed


def test_without_a_key_the_model_is_attached_but_not_trusted(building) -> None:
    pdf = embed_model(_blank_pdf(), building, key=b"")
    found = read_embedded_model(pdf, key=b"")
    assert found is not None and not found.signed


def _blank_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    return doc.tobytes()


def test_boq_uses_the_signed_model_exactly(building, monkeypatch) -> None:
    from app.modules.sheets.boq_service import default_pdf_parser

    monkeypatch.setattr(get_settings(), "model_signing_key", SecretStr(KEY.decode()))
    pdf = embed_model(_blank_pdf(), building)
    plan_json = default_pdf_parser(pdf)
    assert plan_json["generator"]["plan_id"] == building.meta.plan_id
    walls = plan_json["levels"][0]["walls"]
    assert len(walls) == len(building.storeys[0].walls)


def test_vendor_tools_are_not_required_for_the_rest(monkeypatch) -> None:
    """No converter: DWG says so instead of failing silently."""
    from app.modules.ai.floorplan.render import dwg

    monkeypatch.setattr(dwg, "DEFAULT_PATHS", ())
    monkeypatch.setattr(get_settings(), "dwg_converter", "")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(dwg.DwgUnavailable):
        dwg.dxf_to_dwg(b"0\nEOF\n")
