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


@pytest.mark.parametrize(
    ("said", "read"),
    [
        ("a Garage, Four year leading to a courtyard", "a Garage, foyer leading to a courtyard"),
        ("and for year I want a meeting room", "and foyer I want a meeting room"),
        ("And four and courtyard in front", "And foyer and courtyard in front"),
        ("must have a walking wardrobe", "must have a walk-in wardrobe"),
        ("One common washroom", "One common bathroom"),
        ("Pooja room", "puja room"),
        ("a drawing room", "a living room"),
    ],
)
def test_spoken_words_are_corrected_and_shown(said: str, read: str) -> None:
    from app.modules.ai.floorplan.pipeline.brief_parser import fix_spoken_words

    text, notes = fix_spoken_words(said)
    assert text == read and len(notes) == 1 and notes[0].startswith("I read “")


@pytest.mark.parametrize(
    "text",
    [
        "my son is 4 year old",
        "four bedrooms and four bathrooms",
        "south facing villa, 2 bedrooms with attached bathroom and walk in wardrobes",
    ],
)
def test_correct_words_are_left_alone(text: str) -> None:
    from app.modules.ai.floorplan.pipeline.brief_parser import fix_spoken_words

    assert fix_spoken_words(text) == (text, [])


def test_an_unclear_number_becomes_an_assumption_not_a_failure() -> None:
    from app.modules.ai.floorplan.pipeline.brief_parser import unclear_numbers

    notes = unclear_numbers("One Master bedroom 18 on the Ground floor, bedroom 12 x 14 ft")
    assert len(notes) == 1 and "Master bedroom 18" in notes[0]


def test_rules_bind_to_the_room_their_words_name() -> None:
    from types import SimpleNamespace as R

    from app.modules.ai.floorplan.schemas.rules import DoorBetween, Place, Touches, resolve_rules

    rooms = [
        R(id="bath_1", type="bath", label="BATH", attached_to="bed_1"),
        R(id="bath_c1", type="bath", label="COMMON BATH", attached_to=None),
        R(id="foyer_1", type="foyer", label="FOYER", attached_to=None),
        R(id="garden_1", type="garden", label="LAWN", attached_to=None),
        R(id="garden_2", type="garden", label="GARDEN", attached_to=None),
        R(id="pool_1", type="pool", label="SWIMMING POOL", attached_to=None),
    ]
    rules = [
        Place(kind="place", room="garden", side="front", text="in the front yard a lawn"),
        Place(kind="place", room="garden", side="rear", text="in the backyard a garden"),
        Touches(kind="touches", room="pool", others=["garden"], text="garden by the pool"),
        DoorBetween(kind="door_between", a="bath", b="foyer", text="common washroom off foyer"),
    ]
    got = resolve_rules(rules, rooms)
    assert got[0].room == "garden_1" and got[1].room == "garden_2"
    assert got[2].others == ["garden_2"]
    assert got[3].a == "bath_c1"
