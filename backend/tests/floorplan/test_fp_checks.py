"""Engineering checks on the building model (values: docs/pro/2d/RULES.md)."""

import pytest

from app.modules.ai.floorplan.model.build import build_building
from app.modules.ai.floorplan.model.checks import run_checks, summary
from tests.floorplan.test_fp_building import _pool_plan


@pytest.fixture
def building():
    return build_building(_pool_plan(), date="2026-11-20")


def _codes(b) -> dict[str, list]:
    out: dict[str, list] = {}
    for i in run_checks(b):
        out.setdefault(i.code, []).append(i)
    return out


def test_a_room_without_a_door_is_critical(building) -> None:
    st = building.storeys[0]
    bed = next(r for r in st.rooms if r.type == "bedroom")
    openings = [o for o in st.openings if bed.id not in o.rooms or o.kind == "window"]
    b = building.model_copy(update={"storeys": [st.model_copy(update={"openings": openings})]})
    issues = _codes(b)["NO_DOOR"]
    assert issues[0].severity == "critical" and bed.id in issues[0].rooms


def test_narrow_doors_and_small_rooms_are_critical(building) -> None:
    st = building.storeys[0]
    openings = [o.model_copy(update={"width": 700}) if o.kind == "door" else o for o in st.openings]
    rooms = [
        r.model_copy(update={"polygon": [(600, 600), (2600, 600), (2600, 2600), (600, 2600)]})
        if r.type == "bedroom"
        else r
        for r in st.rooms
    ]
    b = building.model_copy(
        update={"storeys": [st.model_copy(update={"openings": openings, "rooms": rooms})]}
    )
    codes = _codes(b)
    assert any(i.severity == "critical" for i in codes["DOOR_WIDTH"])
    assert any("BED" in i.message for i in codes["ROOM_SIZE"])
    assert "critical" in summary(run_checks(b))


def test_stair_limits(building) -> None:
    st = building.storeys[0]
    s = st.stairs[0]
    bad = s.model_copy(update={"riser": 200, "tread": 250, "headroom": 2000})
    b = building.model_copy(update={"storeys": [st.model_copy(update={"stairs": [bad]})]})
    msg = _codes(b)["STAIR"][0].message
    assert "riser 200" in msg and "tread 250" in msg and "headroom 2000" in msg


def test_habitable_room_without_window_and_bath_ventilation(building) -> None:
    st = building.storeys[0]
    openings = [o for o in st.openings if o.kind == "door"]
    b = building.model_copy(update={"storeys": [st.model_copy(update={"openings": openings})]})
    codes = _codes(b)
    assert any(i.severity == "critical" for i in codes["NO_WINDOW"])
    assert codes["VENTILATION"][0].severity == "warning"


def test_setbacks_below_the_dbc_table_are_flagged() -> None:
    b = build_building(_pool_plan())
    b = b.model_copy(
        update={
            "site": b.site.model_copy(
                update={
                    "setbacks": b.site.setbacks.model_copy(update={"left": 1500, "right": 1500})
                }
            )
        }
    )
    codes = _codes(b)
    assert "SETBACK_DBC" in codes
    assert codes["SETBACK"]  # rooms of this whole-plot layout cross the setback line


def test_one_storey_needs_no_wet_stacking(building) -> None:
    assert _codes(building)["WET_STACK"][0].severity == "info"


def test_api_lists_the_checks(sample_plan) -> None:
    from app.modules.ai.floorplan import service
    from app.modules.ai.floorplan.store import StoredPlan

    sp = StoredPlan(id="p", owner_id="u", name="x", plan=sample_plan)
    resp = service.to_response(sp)
    assert resp.checks and {"code", "severity", "message", "rooms", "ref"} <= set(resp.checks[0])
