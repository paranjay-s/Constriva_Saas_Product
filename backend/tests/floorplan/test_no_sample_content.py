"""
Guard test: the 2D floor plan generator must not carry any hard-coded sample plan,
client name or branding from the old reference drawing.

Scope (per docs/plans/2d-floorplan-plan.md, Decision 1): only the floor plan
generator's own files. Other modules (parsing, plans, sheets, 3D viewer) are out of
scope for this task and are deliberately not scanned here.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend"
FRONTEND = REPO_ROOT / "frontend"

# Built from fragments so this file never matches itself.
# Old hard-coded sample drawing, Vastu (removed from scope), and the names/branding
# printed on the developer-only reference image in docs/reference/.
DENY_LIST = [
    "pat" + "odi",
    "gee" + "ta",
    "ga" + "ud",
    "shal" + "imar",
    "vas" + "tu",
    "ham" + "ed",
    "ala" + "wi",
    "gran" + "ada",
]
DENY_RE = re.compile("|".join(DENY_LIST), re.IGNORECASE)

SCANNED_FILES = [
    BACKEND / "app/modules/ai/floorplan_generator.py",
    BACKEND / "app/modules/ai/router.py",
    BACKEND / "tests/unit/test_ai_floorplan.py",
]
SCANNED_DIRS = [
    BACKEND / "app/modules/ai/floorplan",
    BACKEND / "app/modules/ai/llm",
    BACKEND / "app/modules/ai/prompts",
    BACKEND / "tests/floorplan",
    FRONTEND / "src/features/chat",
    FRONTEND / "src/features/floorplan",
    # the chat studio (the UI branch) now holds the generator's brief form, edit chat and
    # project gate that used to live in features/floorplan
    FRONTEND / "src/features/studio",
]
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".ts", ".tsx", ".svg", ".html", ".css"}


def _files_in_scope() -> list[Path]:
    files = [f for f in SCANNED_FILES if f.exists()]
    for d in SCANNED_DIRS:
        if d.exists():
            files.extend(
                p
                for p in d.rglob("*")
                if p.is_file()
                and p.suffix in TEXT_SUFFIXES
                and "__pycache__" not in p.parts
                and p.resolve() != Path(__file__).resolve()
            )
    return files


def test_scope_is_not_empty() -> None:
    assert len(_files_in_scope()) >= 3


@pytest.mark.parametrize("path", _files_in_scope(), ids=lambda p: p.name)
def test_no_sample_content(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    hits = [
        f"{path.relative_to(REPO_ROOT)}:{n}: {line.strip()[:120]}"
        for n, line in enumerate(text.splitlines(), 1)
        if DENY_RE.search(line)
    ]
    assert not hits, "Sample/branding content found:\n" + "\n".join(hits)


def test_rendered_svg_has_no_sample_content(sample_plan) -> None:
    from app.modules.ai.floorplan.render import render_svg

    svg = render_svg(sample_plan)
    assert not DENY_RE.search(svg), DENY_RE.findall(svg)


def test_new_pipeline_does_not_use_old_templates() -> None:
    """The new floorplan package must never import the old hard-coded generator."""
    pkg = BACKEND / "app/modules/ai/floorplan"
    offenders = [
        str(p.relative_to(REPO_ROOT))
        for p in pkg.rglob("*.py")
        if "floorplan_generator" in p.read_text(encoding="utf-8")
    ]
    assert not offenders, offenders


def test_generated_plan_has_no_sample_content() -> None:
    """The old generator's output (title, client, commentary, PlanJSON) is clean."""
    import json
    import os

    os.environ["TESTING"] = "1"
    from app.modules.ai.floorplan_generator import generate_ai_floorplan

    result = generate_ai_floorplan(
        plot_width_ft=30, plot_length_ft=50, config_type="2_bhk", goal="residence"
    )
    result.pop("png_base64")
    blob = json.dumps(result)
    assert not DENY_RE.search(blob), DENY_RE.findall(blob)
    assert result["plan_json"]["client"] == ""
