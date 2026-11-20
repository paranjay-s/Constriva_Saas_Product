"""The three spoken / typed briefs from the owner (A1), with the AI answers replayed from
fixtures/llm_cache (recorded once from claude-opus-5-5; no live calls here)."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = Path(__file__).parent / "fixtures" / "golden"
sys.path.insert(0, str(ROOT / "tools" / "floorplan_cases"))

pytestmark = pytest.mark.site_rules


def _brief_text(name: str) -> str:
    return (GOLDEN / f"{name}.txt").read_text().strip()


@pytest.fixture
def feat_pro_setbacks(monkeypatch):
    """The setbacks feat/pro shipped with (3 m front, 1.5 m sides and rear)."""
    from app.modules.ai.floorplan.settings import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "setback_front_m", 3.0)
    monkeypatch.setattr(s, "setback_side_m", 1.5)
    monkeypatch.setattr(s, "setback_rear_m", 1.5)


def test_the_working_brief_reaches_the_solver_exactly_as_on_feat_pro(feat_pro_setbacks) -> None:
    """Same program, plot, door tree and solver options in the same order as feat/pro.

    The solver is time-limited and multi-threaded, so its own result varies from run to
    run even on feat/pro; what the generator controls is checked here."""
    from solver_inputs import record

    got = record(_brief_text("works"))
    want = json.loads((GOLDEN / "works_solver_inputs.json").read_text())
    assert got[0] == want[0] == {"status": "ok"}
    got_calls = json.loads(json.dumps(got[1:], sort_keys=True))
    # the first call is always made; later ones only if the earlier runs timed out
    assert got_calls[0] == want[1]
    for g, w in zip(got_calls, want[1:], strict=False):
        assert g == w


@pytest.mark.parametrize("name", ["fail1", "fail2"])
def test_the_refused_briefs_now_get_a_plan_with_the_adjustments_listed(name: str) -> None:
    from golden import plan_for

    res = plan_for(_brief_text(name))
    assert res.ok and res.plan is not None
    # brief 1 needs the ladder; brief 2 now fits in the first pass (no setbacks by default
    # and the stated built-up area), so either path is fine as long as a plan comes back
    assert res.report is not None and res.report.ok
    if res.adjustments:
        assert "bring any of these back" in res.message
        assert all(a.endswith(".") for a in res.adjustments)
