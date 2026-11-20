"""DXF -> DWG with the ODA File Converter, run as a separate process.

Measured on 2026-11-20 (docs/pro/DEPENDENCIES.md): the ODA File Converter writes an
AutoCAD 2018 DWG that reads back with the same entities and layers (checked with ODA and,
independently, with GNU LibreDWG's dwg2dxf). LibreDWG's own dxf2dwg could not read our
R2018 DXF and only writes R2000, so it is not used as the writer.

The converter is proprietary freeware from the Open Design Alliance; whether it may run on
a commercial server is for the owner to confirm. It is used only when it is installed:
FLOORPLAN_DWG_CONVERTER, else the usual macOS / Linux paths. Otherwise DwgUnavailable says
so, and DXF stays available.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_PATHS = (
    "/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter",
    "/usr/bin/ODAFileConverter",
    "/usr/local/bin/ODAFileConverter",
    "/opt/ODAFileConverter/ODAFileConverter",
)
TIMEOUT_S = 90
DWG_VERSION = "ACAD2018"


class DwgUnavailable(RuntimeError):
    """DWG export is not set up on this server (DXF is)."""


def converter_path() -> str | None:
    from app.modules.ai.floorplan.settings import get_settings

    configured = get_settings().dwg_converter.strip()
    for candidate in ([configured] if configured else []) + list(DEFAULT_PATHS):
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    found = shutil.which("ODAFileConverter")
    return found


def _run(exe: str, src: Path, dst: Path, fmt: str, pattern: str) -> None:
    env = dict(os.environ)
    if sys.platform.startswith("linux"):  # a server without a display (macOS needs none)
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        subprocess.run(
            [exe, str(src), str(dst), DWG_VERSION, fmt, "0", "1", pattern],
            check=False,
            capture_output=True,
            timeout=TIMEOUT_S,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise DwgUnavailable(f"the DWG converter did not finish ({type(e).__name__})") from e


def dxf_to_dwg(dxf: bytes) -> bytes:
    exe = converter_path()
    if exe is None:
        raise DwgUnavailable(
            "DWG export needs the ODA File Converter on the server (FLOORPLAN_DWG_CONVERTER). "
            "Download the DXF instead; every CAD program opens it."
        )
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "in", Path(tmp) / "out"
        src.mkdir()
        dst.mkdir()
        (src / "plan.dxf").write_bytes(dxf)
        _run(exe, src, dst, "DWG", "*.dxf")
        out = dst / "plan.dwg"
        if not out.is_file() or out.stat().st_size == 0:
            raise DwgUnavailable("the DWG converter produced no file")
        return out.read_bytes()


def dwg_to_dxf(dwg: bytes) -> bytes:
    """Read a DWG back (used by the tests to check what was written)."""
    exe = converter_path()
    if exe is None:
        raise DwgUnavailable("no DWG converter")
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "in", Path(tmp) / "out"
        src.mkdir()
        dst.mkdir()
        (src / "plan.dwg").write_bytes(dwg)
        _run(exe, src, dst, "DXF", "*.dwg")
        out = dst / "plan.dxf"
        if not out.is_file():
            raise DwgUnavailable("the DWG could not be read back")
        return out.read_bytes()
