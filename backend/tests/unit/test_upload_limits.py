"""Upload safety and cost control: both plan upload flows turn away anything that is not
a PDF within the size and page limits, before a job, a stored file or a model call exists.
"""

import pymupdf
import pytest

from app.modules.parsing import router as parsing_router
from app.modules.parsing import service as parsing_service
from app.modules.parsing.errors import (
    FileTooLargeError,
    NotAPdfError,
    PdfInputError,
    PlanParseError,
    TooManyPagesError,
)
from app.modules.parsing.llm_parser import parse_plan_pdf
from app.modules.parsing.pdf_input import check_plan_pdf, load_plan_pdf
from app.modules.parsing.plan_cache import NullPlanCache
from app.modules.parsing.settings import PlanParserSettings, get_settings
from app.modules.sheets.boq_jobs import BoqJobManager, get_boq_jobs
from app.modules.sheets.boq_router import get_pdf_parser

BOQ = "/api/v1/sheets/boq"
IMPORT = "/api/v1/parsing/process"


def pdf(pages: int = 1) -> bytes:
    doc = pymupdf.open()
    for number in range(pages):
        page = doc.new_page(width=420, height=297)
        page.insert_text((60, 80), f"FLOOR PLAN {number + 1}", fontsize=11)
        page.draw_rect(pymupdf.Rect(40, 40, 380, 260))
    data = doc.tobytes()
    doc.close()
    return data


class CountingLLM:
    provider, model, last_usage = "fake", "fake-1", None

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(self, **_kw):
        self.calls += 1
        raise AssertionError("the model must not be called for a rejected upload")


# ------------------------------------------------------------------------- the check


def test_defaults_are_20_mb_and_10_pages():
    fields = PlanParserSettings.model_fields
    assert fields["max_pdf_mb"].default == 20.0
    assert fields["max_pdf_pages"].default == 10
    assert PlanParserSettings.model_construct(max_pdf_mb=20.0).max_pdf_bytes == 20 * 1024 * 1024


def test_limits_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("PLAN_PARSER_MAX_PDF_MB", "5")
    monkeypatch.setenv("PLAN_PARSER_MAX_PDF_PAGES", "3")
    settings = PlanParserSettings()
    assert (settings.max_pdf_mb, settings.max_pdf_pages) == (5.0, 3)


def test_a_normal_pdf_passes_and_reports_its_page_count():
    assert check_plan_pdf(pdf(pages=2), "Plan.PDF") == 2


@pytest.mark.parametrize("name", ["plan.png", "plan.dwg", "plan.pdf.exe", "plan"])
def test_only_pdf_file_names_are_accepted(name):
    with pytest.raises(NotAPdfError, match="as a PDF"):
        check_plan_pdf(pdf(), name)


def test_a_file_named_pdf_that_is_not_one_is_rejected():
    with pytest.raises(NotAPdfError, match="not a PDF"):
        check_plan_pdf(b"\x89PNG\r\n\x1a\n" + b"0" * 200, "plan.pdf")
    with pytest.raises(PdfInputError, match="empty"):
        check_plan_pdf(b"", "plan.pdf")
    with pytest.raises(PdfInputError, match="could not be opened"):
        check_plan_pdf(b"%PDF-1.7\nthis is not really a pdf", "plan.pdf")


def test_size_limit_message_names_the_size_and_the_limit():
    data = pdf()
    with pytest.raises(FileTooLargeError) as caught:
        check_plan_pdf(data + b"\n" * (3 * 1024 * 1024), "plan.pdf", max_bytes=2 * 1024 * 1024)
    assert caught.value.http_status == 413 and caught.value.code == "file_too_large"
    assert "The largest file accepted is 2 MB" in caught.value.message
    assert "This PDF is 3.0 MB" in caught.value.message


def test_page_limit_message_names_the_count_and_the_limit():
    with pytest.raises(TooManyPagesError) as caught:
        check_plan_pdf(pdf(pages=11), "plan.pdf")
    assert caught.value.http_status == 400 and caught.value.code == "too_many_pages"
    assert "has 11 pages" in caught.value.message and "at most 10 pages" in caught.value.message
    assert check_plan_pdf(pdf(pages=10), "plan.pdf") == 10


def test_every_rejection_is_a_typed_parse_error_with_a_user_message():
    for error in (NotAPdfError("x"), FileTooLargeError("x"), TooManyPagesError("x")):
        assert isinstance(error, PlanParseError) and isinstance(error, ValueError)
        assert error.to_dict()["code"] == error.code


# ------------------------------------------------- the parser itself is guarded too


def test_the_parser_rejects_an_oversized_pdf_before_any_model_call(monkeypatch):
    llm = CountingLLM()
    with pytest.raises(TooManyPagesError):
        parse_plan_pdf(pdf(pages=11), client=llm, cache=NullPlanCache())
    monkeypatch.setattr(get_settings(), "max_pdf_mb", 0.001)  # about 1 KB
    with pytest.raises(FileTooLargeError):
        parse_plan_pdf(pdf() + b"\n" * 4096, client=llm, cache=NullPlanCache())
    assert llm.calls == 0


def test_pages_are_never_silently_dropped():
    with pytest.raises(TooManyPagesError):
        load_plan_pdf(pdf(pages=3), max_pages=2)
    assert len(load_plan_pdf(pdf(pages=3), max_pages=3).pages) == 3


# --------------------------------------------------------------------- both endpoints


@pytest.fixture
def guarded(client, monkeypatch):
    """Both upload endpoints, with every step past the upload check made to fail loudly."""
    from app.main import app

    reached: list[str] = []

    def boq_parser(_data: bytes) -> dict:
        reached.append("boq parser")
        raise AssertionError("parser reached")

    app.dependency_overrides[get_pdf_parser] = lambda: boq_parser
    app.dependency_overrides[get_boq_jobs] = lambda: BoqJobManager()
    monkeypatch.setattr(
        parsing_router, "ensure_project_exists", lambda *a, **k: reached.append("project")
    )
    monkeypatch.setattr(parsing_router, "get_supabase_client", lambda: reached.append("database"))
    monkeypatch.setattr(parsing_service, "parse_plan_pdf", lambda *a, **k: reached.append("parser"))
    client.reached = reached
    return client


def post(client, url: str, name: str, content: bytes):
    return client.post(url, files={"file": (name, content, "application/pdf")})


@pytest.mark.parametrize("url", [BOQ, IMPORT])
def test_both_flows_accept_pdf_only(guarded, url):
    response = post(guarded, url, "plan.png", pdf())
    assert response.status_code == 400
    assert response.json()["detail"] == "Please upload the floor plan as a PDF file."
    response = post(guarded, url, "plan.pdf", b"GIF89a not a pdf at all")
    assert response.status_code == 400 and "not a PDF" in response.json()["detail"]
    assert guarded.reached == []


@pytest.mark.parametrize("url", [BOQ, IMPORT])
def test_both_flows_enforce_the_page_limit(guarded, url):
    response = post(guarded, url, "plan.pdf", pdf(pages=11))
    assert response.status_code == 400
    assert "has 11 pages" in response.json()["detail"] and "at most 10" in response.json()["detail"]
    assert guarded.reached == []


@pytest.mark.parametrize("url", [BOQ, IMPORT])
def test_both_flows_enforce_the_size_limit(guarded, url, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_pdf_mb", 0.001)  # about 1 KB
    response = post(guarded, url, "plan.pdf", pdf() + b"\n" * 4096)
    assert response.status_code == 413
    assert "largest file accepted" in response.json()["detail"]
    assert guarded.reached == []  # no project, no job, no stored file, no model call


@pytest.mark.parametrize("url", [BOQ, IMPORT])
def test_both_flows_follow_a_limit_changed_by_env(guarded, url, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_pdf_pages", 2)
    response = post(guarded, url, "plan.pdf", pdf(pages=3))
    assert response.status_code == 400 and "at most 2 pages" in response.json()["detail"]
    assert guarded.reached == []


def test_the_limits_are_published_for_the_upload_screens(client, monkeypatch):
    assert client.get("/api/v1/parsing/upload-limits").json() == {
        "max_pdf_mb": 20.0,
        "max_pdf_pages": 10,
    }
    monkeypatch.setattr(get_settings(), "max_pdf_mb", 8.0)
    monkeypatch.setattr(get_settings(), "max_pdf_pages", 4)
    assert client.get("/api/v1/parsing/upload-limits").json() == {
        "max_pdf_mb": 8.0,
        "max_pdf_pages": 4,
    }
