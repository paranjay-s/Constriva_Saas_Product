"""Saved bills of quantities (sheets/boq_history.py): each finished BOQ is kept for its owner."""

import pytest

from app.modules.sheets import boq_history
from app.modules.sheets.boq_history import MemoryHistoryStore, set_history_store
from tests.unit.test_boq import boq_client, minimal_pdf, plan, wait_for_job  # noqa: F401 (fixtures)


@pytest.fixture
def history():
    store = MemoryHistoryStore()
    set_history_store(store)
    yield store
    set_history_store(None)


def test_a_finished_bill_is_saved_and_listed_for_its_owner_only(boq_client, history):  # noqa: F811
    started = boq_client.post(
        "/api/v1/sheets/boq", files={"file": ("Villa A.pdf", minimal_pdf(), "application/pdf")}
    )
    wait_for_job(boq_client, started.json()["job_id"])
    listed = boq_client.get("/api/v1/sheets/boq/history")
    assert listed.status_code == 200
    (bill,) = listed.json()["bills"]
    assert bill["name"] == "Villa A.pdf" and bill["source"] == "upload"
    assert bill["summary"]["items"] == 64 and "result" not in bill  # lists carry the summary only
    assert bill["summary"]["area_m2"] and bill["summary"]["levels"]
    whole = boq_client.get(f"/api/v1/sheets/boq/history/{bill['id']}").json()
    assert len(whole["result"]["items"]) == 64
    # another user sees nothing and cannot open or delete it
    other = history.list_for_user("someone-else")
    assert other == [] and history.get("someone-else", bill["id"]) is None
    assert not history.delete("someone-else", bill["id"])
    assert boq_client.delete(f"/api/v1/sheets/boq/history/{bill['id']}").status_code == 204
    assert boq_client.get(f"/api/v1/sheets/boq/history/{bill['id']}").status_code == 404
    assert boq_client.get("/api/v1/sheets/boq/history").json()["bills"] == []


def test_a_failed_save_never_fails_the_bill(boq_client, monkeypatch):  # noqa: F811
    class Broken(MemoryHistoryStore):
        def save(self, *a, **k):
            raise RuntimeError("relation boq_history does not exist")

    set_history_store(Broken())
    try:
        started = boq_client.post(
            "/api/v1/sheets/boq", files={"file": ("p.pdf", minimal_pdf(), "application/pdf")}
        )
        assert wait_for_job(boq_client, started.json()["job_id"])["status"] == "done"
    finally:
        set_history_store(None)


def test_summary_of_a_bill():
    s = boq_history.summary(
        {
            "items": [{"quote_status": "INCLUDED"}, {"quote_status": "EXCLUDED_FROM_QUOTE"}],
            "warnings": ["x"],
            "geometry_summary": {"total_area_m2": 312.345, "levels": [1, 2]},
        }
    )
    assert s == {
        "items": 2,
        "in_quote": 1,
        "levels": 2,
        "area_m2": 312.3,
        "warnings": 1,
        "rooms": None,
    }
