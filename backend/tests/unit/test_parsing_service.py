"""The blueprint import service: what happens when the plan parser fails, and when it works.

Supabase, storage and the parser are all replaced here; nothing touches the network.
"""

import asyncio
import inspect
from unittest.mock import MagicMock

import pytest

from app.modules.parsing import service as parsing_service
from app.modules.parsing.errors import NoFloorPlanError, PlanOutputInvalidError
from app.modules.parsing.service import ParsingService
from app.modules.plans import router as plans_router


class FakeSupabase:
    """Records every table write as (table, operation, payload)."""

    def __init__(self) -> None:
        self.writes: list[tuple[str, str, dict]] = []
        self.storage = MagicMock()
        self.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://x/y"
        }

    def table(self, name: str) -> "FakeSupabase._Table":
        return FakeSupabase._Table(self, name)

    class _Table:
        def __init__(self, db: "FakeSupabase", name: str) -> None:
            self.db, self.name = db, name

        def insert(self, payload: dict) -> "FakeSupabase._Table":
            self.db.writes.append((self.name, "insert", payload))
            return self

        def update(self, payload: dict) -> "FakeSupabase._Table":
            self.db.writes.append((self.name, "update", payload))
            return self

        def eq(self, *_args) -> "FakeSupabase._Table":
            return self

        def execute(self) -> MagicMock:
            return MagicMock(data=[])


PLAN = {
    "schema_version": "2.0",
    "units": "m",
    "levels": [{"rooms": [{"id": "L0-R01"}] * 7, "walls": [], "openings": [], "columns": []}],
    "confidence": {"overall": 0.8},
}


@pytest.fixture
def db(monkeypatch) -> FakeSupabase:
    fake = FakeSupabase()
    monkeypatch.setattr(parsing_service, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(parsing_service, "ensure_storage_buckets", lambda: None)
    monkeypatch.setattr(
        parsing_service, "upload_to_storage", lambda **kw: f"{kw['bucket_name']}/{kw['file_path']}"
    )
    monkeypatch.setattr(
        parsing_service, "convert_pdf_page_to_png", lambda *a, **kw: (b"png", 10, 10)
    )
    return fake


def run_import(monkeypatch, parser):
    monkeypatch.setattr(parsing_service, "parse_plan_pdf", parser)
    return asyncio.run(
        ParsingService.process_blueprint_pdf(
            pdf_bytes=b"%PDF-1.7 fake",
            filename="client plan.pdf",
            project_id="11111111-1111-1111-1111-111111111111",
            user_id="22222222-2222-2222-2222-222222222222",
            job_id="33333333-3333-3333-3333-333333333333",
        )
    )


def test_parse_failure_fails_the_job_with_the_typed_error_and_saves_no_plan(db, monkeypatch):
    def failing_parser(_pdf, **_kw):
        raise PlanOutputInvalidError(
            "The floor plan could not be read reliably.", details=["bad wall"]
        )

    result = run_import(monkeypatch, failing_parser)

    assert result == {
        "status": "failed",
        "error": {
            "code": "llm_output_invalid",
            "message": "The floor plan could not be read reliably.",
            "details": ["bad wall"],
        },
    }
    # no plan row at all: nothing is substituted for the plan that could not be read
    assert [w for w in db.writes if w[0] == "plans"] == []
    assert [w for w in db.writes if w[0] == "projects"] == []
    final = [w for w in db.writes if w[0] == "jobs" and w[1] == "update"][-1][2]
    assert final["status"] == "failed"
    assert final["step"] == "The floor plan could not be read reliably."
    assert final["result"] == result
    assert "finished_at" in final


def test_every_typed_parse_error_is_passed_through(db, monkeypatch):
    def no_plan(_pdf, **_kw):
        raise NoFloorPlanError("No floor plan was found in this PDF.")

    result = run_import(monkeypatch, no_plan)
    assert result["error"]["code"] == "no_floor_plan"
    assert all(w[0] != "plans" for w in db.writes)


def test_successful_parse_saves_exactly_the_parsed_plan(db, monkeypatch):
    result = run_import(monkeypatch, lambda _pdf, **_kw: PLAN)
    plans = [w[2] for w in db.writes if w[0] == "plans" and w[1] == "insert"]
    assert len(plans) == 1
    assert plans[0]["plan_json"] is PLAN  # the parser's output, untouched
    assert plans[0]["origin"] == "extracted"
    assert result["plan_data"] is PLAN
    final = [w for w in db.writes if w[0] == "jobs" and w[1] == "update"][-1][2]
    assert final["status"] == "done" and final["progress"] == 100
    assert final["result"]["plan_summary"]["rooms_count"] == 7


def test_the_import_asks_the_parser_for_a_complete_plan(db, monkeypatch):
    seen = {}

    def parser(pdf, **kw):
        seen.update(kw, pdf=pdf)
        return PLAN

    run_import(monkeypatch, parser)
    assert seen == {"pdf": b"%PDF-1.7 fake", "min_rooms": parsing_service.BLUEPRINT_MIN_ROOMS}


def test_no_template_plan_or_hard_coded_client_remains_in_the_import_or_download_paths():
    for module in (parsing_service, plans_router):
        source = inspect.getsource(module)
        assert "create_architectural_template" not in source
        assert "build_plan_json_from_template" not in source
        assert "GEETA" not in source


def test_downloading_a_drawing_that_does_not_exist_is_a_404_not_another_plan(client, fake_db):
    fake_db()  # an empty database
    response = client.get("/api/v1/plans/44444444-4444-4444-4444-444444444444/download-png")
    assert response.status_code == 404
    assert response.json()["detail"] == "This plan has no downloadable drawing."
