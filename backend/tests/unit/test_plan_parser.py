"""The PDF -> PlanJSON pipeline, with a fake LLM client. No network is used."""

import copy
import json
import logging
from pathlib import Path

import pymupdf
import pytest

from app.modules.ai.llm.json_client import (
    LLMAuthenticationError,
    LLMBillingError,
    LLMImage,
    LLMInvalidJSONError,
    LLMNotConfiguredError,
    LLMRateLimitError,
    LLMRequestRejectedError,
    LLMUnavailableError,
    LLMUsage,
)
from app.modules.parsing import llm_parser
from app.modules.parsing.errors import (
    NoFloorPlanError,
    ParserAuthError,
    ParserBillingError,
    ParserNotConfiguredError,
    ParserRateLimitedError,
    ParserRequestRejectedError,
    ParserUnavailableError,
    PdfInputError,
    PlanOutputInvalidError,
    PlanParseError,
)
from app.modules.parsing.llm_parser import (
    MAX_REPAIR_ATTEMPTS,
    PARSER_VERSION,
    load_prompt,
    parse_plan_images,
    parse_plan_pdf,
)
from app.modules.parsing.llm_schema import WIRE_JSON_SCHEMA
from app.modules.parsing.pdf_input import (
    MAX_IMAGE_SIDE_PX,
    RENDER_DPI,
    effective_dpi,
    load_plan_pdf,
)
from app.modules.parsing.plan_cache import FilePlanCache, plan_cache_key, reply_cache_key
from app.modules.plans.schemas import SCHEMA_VERSION, PlanJSON

EXTRACTED_PLAN = Path(__file__).resolve().parents[2] / "extracted_plan.json"
# Fingerprint of the prompt text, the wire schema and the render settings (see the test
# that uses it). It changes only together with the prompt version.
SENT_TO_MODEL_FINGERPRINT = "405916461b697d2f"
IMAGES = [LLMImage(b"not-a-real-png")]


class FakeLLM:
    """Replays scripted replies. A reply that is an exception is raised instead."""

    provider = "fake"
    model = "fake-1"

    def __init__(self, *replies, model: str = "fake-1", usage: LLMUsage | None = None):
        self.replies = list(replies)
        self.calls: list[dict] = []
        self.model = model
        self.last_usage = usage

    def generate_json(self, *, system_prompt, images, text, json_schema=None):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "images": images,
                "text": text,
                "json_schema": json_schema,
            }
        )
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return copy.deepcopy(reply)


def good_reply() -> dict:
    return {
        "units": "m",
        "building_type": "villa",
        "scale_source": "dimension_label",
        "project_title": "Test House",
        "levels": [
            {
                "index": 0,
                "name": "Ground Floor",
                "wall_height": None,
                "wall_height_source": "default",
                "rooms": [
                    {
                        "id": "r1",
                        "name": "BEDROOM",
                        "kind": "indoor",
                        "polygon": [[0, 0], [4, 0], [4, 5], [0, 5]],
                    },
                    {
                        "id": "r2",
                        "name": "KITCHEN",
                        "kind": "indoor",
                        "polygon": [[4, 0], [8, 0], [8, 5], [4, 5]],
                    },
                ],
                "walls": [
                    {
                        "id": "w1",
                        "start": [0, 0],
                        "end": [8, 0],
                        "thickness": 0.23,
                        "kind": "exterior",
                    },
                    {
                        "id": "w2",
                        "start": [8, 0],
                        "end": [8, 5],
                        "thickness": 0.23,
                        "kind": "exterior",
                    },
                    {
                        "id": "w3",
                        "start": [8, 5],
                        "end": [0, 5],
                        "thickness": 0.23,
                        "kind": "exterior",
                    },
                    {
                        "id": "w4",
                        "start": [0, 5],
                        "end": [0, 0],
                        "thickness": 0.23,
                        "kind": "exterior",
                    },
                    {
                        "id": "w5",
                        "start": [4, 0],
                        "end": [4, 5],
                        "thickness": 0.115,
                        "kind": "interior",
                    },
                ],
                "openings": [
                    {
                        "id": "o1",
                        "wall_id": "w5",
                        "type": "door",
                        "offset": 2.5,
                        "width": 0.9,
                        "height": 2.1,
                        "sill": 0,
                    }
                ],
                "columns": [],
            }
        ],
    }


def broken_reply() -> dict:
    reply = good_reply()
    reply["levels"][0]["openings"][0]["wall_id"] = "w99"
    return reply


def make_pdf(pages: int = 1, text: str = "BEDROOM 12' X 14'") -> bytes:
    doc = pymupdf.open()
    for _ in range(pages):
        page = doc.new_page(width=420, height=297)
        page.insert_text((60, 80), text, fontsize=11)
        page.draw_rect(pymupdf.Rect(40, 40, 380, 260))
    data = doc.tobytes()
    doc.close()
    return data


# ------------------------------------------------------------------- valid output


def test_valid_output_becomes_plan_json():
    llm = FakeLLM(good_reply())
    plan = parse_plan_images(IMAGES, ["BEDROOM"], client=llm)
    PlanJSON.model_validate(plan)
    assert plan["schema_version"] == SCHEMA_VERSION
    assert plan["units"] == "m"
    assert plan["building_type"] == "villa"
    assert plan["warnings"] == []
    level = plan["levels"][0]
    assert [r["id"] for r in level["rooms"]] == ["L0-R01", "L0-R02"]
    assert level["openings"][0]["wall_id"] in {w["id"] for w in level["walls"]}
    assert plan["parser"] == {
        "pdf_sha256": None,
        "parser_version": PARSER_VERSION,
        "prompt_version": load_prompt()[1],
        "provider": "fake",
        "model": "fake-1",
        "input_tokens": 0,
        "output_tokens": 0,
        "attempts": 1,
    }
    assert len(llm.calls) == 1


def test_the_model_gets_the_prompt_file_the_page_text_and_the_schema():
    llm = FakeLLM(good_reply())
    parse_plan_images(IMAGES, ["BEDROOM 12' X 14'"], client=llm)
    call = llm.calls[0]
    assert call["system_prompt"] == load_prompt()[0]
    assert "prompt_version" not in call["system_prompt"]
    assert "BEDROOM 12' X 14'" in call["text"]
    assert call["images"] == IMAGES
    assert call["json_schema"] is WIRE_JSON_SCHEMA


def test_same_model_output_gives_identical_plan_json():
    first = parse_plan_images(IMAGES, [""], client=FakeLLM(good_reply()))
    second = parse_plan_images(IMAGES, [""], client=FakeLLM(good_reply()))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


# ------------------------------------------------------------ invalid, then repaired


def test_invalid_output_is_repaired_with_the_validation_errors():
    llm = FakeLLM(broken_reply(), good_reply())
    plan = parse_plan_images(IMAGES, [""], client=llm)
    assert len(plan["levels"][0]["openings"]) == 1
    assert len(llm.calls) == 2
    repair = llm.calls[1]["text"]
    assert "'w99' is not the id of a wall in this level" in repair
    assert '"wall_id":"w99"' in repair  # the previous reply is sent back
    assert "corrected JSON object" in repair


def test_a_reply_that_is_not_json_is_repaired_too():
    llm = FakeLLM(
        LLMInvalidJSONError("The model reply is not a JSON object.", "Sure! Here is"), good_reply()
    )
    plan = parse_plan_images(IMAGES, [""], client=llm)
    assert plan["levels"][0]["rooms"]
    assert "not a JSON object" in llm.calls[1]["text"]
    assert "Sure! Here is" in llm.calls[1]["text"]


def test_schema_errors_are_reported_with_their_path():
    wrong_type = good_reply()
    wrong_type["levels"][0]["walls"][0]["start"] = ["12'6\"", 0]
    llm = FakeLLM(wrong_type, good_reply())
    parse_plan_images(IMAGES, [""], client=llm)
    assert "levels[0].walls[0].start[0]" in llm.calls[1]["text"]


def test_too_few_rooms_is_sent_back_for_repair():
    sparse = good_reply()
    sparse["levels"][0]["rooms"] = sparse["levels"][0]["rooms"][:1]
    llm = FakeLLM(sparse, good_reply())
    plan = parse_plan_images(IMAGES, [""], client=llm, min_rooms=2)
    assert len(plan["levels"][0]["rooms"]) == 2
    assert "only 1 usable room(s)" in llm.calls[1]["text"]


def test_placeholder_names_from_the_prompt_are_rejected():
    echoed = good_reply()
    echoed["levels"][0]["rooms"][0]["name"] = "<room label as printed, with its dimension text>"
    llm = FakeLLM(echoed, good_reply())
    parse_plan_images(IMAGES, [""], client=llm)
    assert "placeholder" in llm.calls[1]["text"]


# -------------------------------------------------------------- unrecoverable output


def test_unrecoverable_output_raises_a_typed_error_and_returns_nothing():
    llm = FakeLLM(broken_reply(), broken_reply(), broken_reply())
    with pytest.raises(PlanOutputInvalidError) as caught:
        parse_plan_images(IMAGES, [""], client=llm)
    error = caught.value
    assert error.code == "llm_output_invalid"
    assert any("'w99' is not the id of a wall" in d for d in error.details)
    assert error.to_dict()["code"] == "llm_output_invalid"
    assert isinstance(error, PlanParseError) and isinstance(error, ValueError)
    assert len(llm.calls) == 1 + MAX_REPAIR_ATTEMPTS  # first try + 2 repairs, no more


def test_missing_levels_is_unrecoverable():
    llm = FakeLLM({"rooms": []}, {"levels": []}, {"levels": "none"})
    with pytest.raises(PlanOutputInvalidError):
        parse_plan_images(IMAGES, [""], client=llm)


def test_provider_outage_raises_parser_unavailable():
    with pytest.raises(ParserUnavailableError) as caught:
        parse_plan_images(IMAGES, [""], client=FakeLLM(LLMUnavailableError("HTTP 503")))
    assert caught.value.code == "llm_unavailable"
    assert caught.value.details == ["HTTP 503"]


def test_missing_key_raises_parser_not_configured():
    with pytest.raises(ParserNotConfiguredError) as caught:
        parse_plan_images(IMAGES, [""], client=FakeLLM(LLMNotConfiguredError("No Gemini API key.")))
    assert caught.value.code == "llm_not_configured"


def test_no_images_is_an_error():
    with pytest.raises(PlanParseError):
        parse_plan_images([], [], client=FakeLLM(good_reply()))


# --------------------------------------------------------------- scale and no plan


def mis_scaled_reply() -> dict:
    """Rooms drawn at a fraction of the sizes their labels state."""
    reply = good_reply()
    level = reply["levels"][0]
    level["rooms"] = [
        {
            "id": "r1",
            "name": "BEDROOM 12' X 14'",
            "kind": "indoor",
            "polygon": [[0, 0], [2, 0], [2, 2], [0, 2]],
        },
        {
            "id": "r2",
            "name": "KITCHEN 10' X 10'",
            "kind": "indoor",
            "polygon": [[2, 0], [4, 0], [4, 2], [2, 2]],
        },
        {
            "id": "r3",
            "name": "LIVING 15' X 20'",
            "kind": "indoor",
            "polygon": [[4, 0], [8, 0], [8, 3], [4, 3]],
        },
    ]
    return reply


def well_scaled_reply() -> dict:
    reply = good_reply()
    level = reply["levels"][0]
    level.update({"overall_width": 11.28, "overall_depth": 6.1})
    level["rooms"] = [
        {
            "id": "r1",
            "name": "BEDROOM 12' X 14'",
            "kind": "indoor",
            "polygon": [[0, 0], [3.66, 0], [3.66, 4.27], [0, 4.27]],
        },
        {
            "id": "r2",
            "name": "KITCHEN 10' X 10'",
            "kind": "indoor",
            "polygon": [[3.66, 0], [6.71, 0], [6.71, 3.05], [3.66, 3.05]],
        },
        {
            "id": "r3",
            "name": "LIVING 15' X 20'",
            "kind": "indoor",
            "polygon": [[6.71, 0], [11.28, 0], [11.28, 6.1], [6.71, 6.1]],
        },
    ]
    level["walls"] = [
        {"id": "w1", "start": [0, 0], "end": [11.28, 0], "kind": "exterior"},
        {"id": "w2", "start": [11.28, 0], "end": [11.28, 6.1], "kind": "exterior"},
        {"id": "w3", "start": [11.28, 6.1], "end": [0, 6.1], "kind": "exterior"},
        {"id": "w4", "start": [0, 6.1], "end": [0, 0], "kind": "exterior"},
    ]
    level["openings"] = []
    return reply


def test_a_mis_scaled_plan_is_sent_back_with_the_evidence():
    llm = FakeLLM(mis_scaled_reply(), well_scaled_reply())
    plan = parse_plan_images(IMAGES, [""], client=llm)
    assert len(llm.calls) == 2
    assert "rooms are drawn at about" in llm.calls[1]["text"]
    assert "Convert each printed dimension to metres" in llm.calls[1]["text"]
    assert plan["warnings"] == []
    areas = sorted(
        round(r["polygon"][2][0] * r["polygon"][2][1] - 0, 1)
        for r in plan["levels"][0]["rooms"][:1]
    )
    assert areas == [15.6]  # 12' x 14' in m2


def test_a_plan_that_stays_mis_scaled_is_kept_with_warnings_not_dropped():
    llm = FakeLLM(mis_scaled_reply(), mis_scaled_reply(), mis_scaled_reply())
    plan = parse_plan_images(IMAGES, [""], client=llm)
    assert len(llm.calls) == 1 + MAX_REPAIR_ATTEMPTS
    assert len(plan["levels"][0]["rooms"]) == 3
    assert sum("but its label states" in w for w in plan["warnings"]) == 3


def test_extent_must_match_the_reported_overall_size():
    wrong = well_scaled_reply()
    wrong["levels"][0].update({"overall_width": 20.0, "overall_depth": 12.0})
    llm = FakeLLM(wrong, well_scaled_reply())
    parse_plan_images(IMAGES, [""], client=llm)
    assert "the overall size you reported is 20.00 x 12.00 m" in llm.calls[1]["text"]


def test_an_outage_during_a_scale_repair_keeps_the_reply_already_in_hand():
    llm = FakeLLM(mis_scaled_reply(), LLMUnavailableError("HTTP 503"))
    plan = parse_plan_images(IMAGES, [""], client=llm)
    assert len(plan["levels"][0]["rooms"]) == 3 and plan["warnings"]


def test_each_level_is_moved_to_its_own_origin():
    shifted = good_reply()
    level = shifted["levels"][0]
    for room in level["rooms"]:
        room["polygon"] = [[x + 11.2, y + 0.8] for x, y in room["polygon"]]
    for wall in level["walls"]:
        wall["start"] = [wall["start"][0] + 11.2, wall["start"][1] + 0.8]
        wall["end"] = [wall["end"][0] + 11.2, wall["end"][1] + 0.8]
    moved = parse_plan_images(IMAGES, [""], client=FakeLLM(shifted))
    plain = parse_plan_images(IMAGES, [""], client=FakeLLM(good_reply()))
    assert moved["levels"] == plain["levels"]
    assert moved["levels"][0]["rooms"][0]["polygon"][0] == [0.0, 0.0]


def test_a_pdf_without_a_floor_plan_is_reported_at_once():
    llm = FakeLLM({"floor_plan_found": False, "levels": []})
    with pytest.raises(NoFloorPlanError) as caught:
        parse_plan_images(IMAGES, [""], client=llm)
    assert caught.value.code == "no_floor_plan"
    assert len(llm.calls) == 1  # nothing to repair


def test_blank_pages_never_reach_the_model(tmp_path):
    doc = pymupdf.open()
    doc.new_page()
    blank = doc.tobytes()
    doc.close()
    llm = FakeLLM(good_reply())
    with pytest.raises(PdfInputError, match="blank"):
        parse_plan_pdf(blank, client=llm, cache=FilePlanCache(tmp_path))
    assert llm.calls == []


# ---------------------------------------------------------------- old-schema JSON


def test_old_schema_reply_is_accepted_and_upgraded():
    """A model (or an older prompt) that answers in the 1.x shape still parses."""
    old = json.loads(EXTRACTED_PLAN.read_text(encoding="utf-8"))
    assert "schema_version" not in old and "index" not in old["levels"][0]
    plan = parse_plan_images(IMAGES, [""], client=FakeLLM(old), min_rooms=6)
    PlanJSON.model_validate(plan)
    assert plan["schema_version"] == SCHEMA_VERSION
    level = plan["levels"][0]
    assert level["index"] == 0 and level["wall_height_source"] == "default"
    assert len(level["rooms"]) == len(old["levels"][0]["rooms"])
    assert all(w["is_exterior"] is (w["kind"] == "exterior") for w in level["walls"])
    assert all(o["sill_height"] == o["sill"] for o in level["openings"])
    assert plan["client"] == "SMT. GEETA GAUD"


# ------------------------------------------------------------------- PDF and cache


def test_pdf_input_renders_pages_and_reads_text():
    pdf = load_plan_pdf(make_pdf(pages=2), max_pages=4)
    assert pdf.page_count == 2 and len(pdf.pages) == 2
    page = pdf.pages[0]
    assert page.png.startswith(b"\x89PNG") and page.dpi == RENDER_DPI
    assert (page.width_px, page.height_px) == (1750, 1238)
    assert page.text == "BEDROOM 12' X 14'"
    assert len(pdf.sha256) == 64


def test_pdf_input_is_identical_for_identical_bytes():
    data = make_pdf()
    first, second = load_plan_pdf(data), load_plan_pdf(data)
    assert first.sha256 == second.sha256
    assert first.pages[0].png == second.pages[0].png and first.pages[0].text == second.pages[0].text


def test_large_sheets_are_scaled_by_a_fixed_rule():
    assert effective_dpi(595, 842) == RENDER_DPI  # A4
    assert effective_dpi(1191, 842) == RENDER_DPI  # A3
    assert effective_dpi(2384, 1684) < RENDER_DPI  # A1
    assert effective_dpi(2384, 1684) == effective_dpi(1684, 2384)


def test_bad_pdf_raises_a_typed_input_error():
    with pytest.raises(PdfInputError) as empty:
        load_plan_pdf(b"")
    assert empty.value.code == "invalid_pdf"
    with pytest.raises(PlanParseError) as not_pdf:
        load_plan_pdf(b"this is not a pdf")
    assert not_pdf.value.code == "not_a_pdf"


def test_parse_plan_pdf_runs_the_whole_pipeline(tmp_path):
    llm = FakeLLM(good_reply())
    data = make_pdf()
    plan = parse_plan_pdf(data, client=llm, cache=FilePlanCache(tmp_path))
    assert plan["parser"]["pdf_sha256"] == load_plan_pdf(data).sha256
    assert llm.calls[0]["images"][0].data.startswith(b"\x89PNG")
    assert "BEDROOM 12' X 14'" in llm.calls[0]["text"]


def test_same_pdf_is_parsed_once_and_then_served_from_the_cache(tmp_path):
    cache = FilePlanCache(tmp_path)
    data = make_pdf()
    llm = FakeLLM(good_reply())
    first = parse_plan_pdf(data, client=llm, cache=cache)
    again = parse_plan_pdf(data, client=FakeLLM(), cache=cache)  # would fail if it called the model
    assert again == first
    assert len(llm.calls) == 1
    # one entry for the plan and one for the model reply it was built from
    names = sorted(path.name for path in tmp_path.glob("*.json"))
    assert len(names) == 2 and ".reply." in names[1] and ".parser-" in names[0]


def test_cache_key_holds_everything_that_decides_the_result():
    key = plan_cache_key("abc", "2.0.0", "2.0.0", "gemini", "model-a")
    assert key.startswith("abc.") and f"schema-{SCHEMA_VERSION}" in key
    assert key.endswith(".gemini.model-a")
    assert plan_cache_key("abc", "2.0.1", "2.0.0", "gemini", "model-a") != key
    assert plan_cache_key("abc", "2.0.0", "2.0.1", "gemini", "model-a") != key
    assert plan_cache_key("abd", "2.0.0", "2.0.0", "gemini", "model-a") != key
    assert plan_cache_key("abc", "2.0.0", "2.0.0", "anthropic", "model-a") != key
    assert plan_cache_key("abc", "2.0.0", "2.0.0", "gemini", "model-b") != key


def test_switching_model_parses_again_instead_of_returning_the_older_result(tmp_path):
    cache = FilePlanCache(tmp_path)
    data = make_pdf()
    first = parse_plan_pdf(data, client=FakeLLM(good_reply(), model="model-a"), cache=cache)

    other = FakeLLM(good_reply(), model="model-b")
    second = parse_plan_pdf(data, client=other, cache=cache)
    assert len(other.calls) == 1  # not answered from model-a's entry
    assert (first["parser"]["model"], second["parser"]["model"]) == ("model-a", "model-b")
    assert len(list(tmp_path.glob("*.json"))) == 4  # a plan and a reply for each model

    # each model still gets its own cached result back
    assert parse_plan_pdf(data, client=FakeLLM(model="model-a"), cache=cache) == first
    assert parse_plan_pdf(data, client=FakeLLM(model="model-b"), cache=cache) == second


def test_a_new_parser_version_builds_the_plan_again_without_calling_the_model(
    tmp_path, monkeypatch, caplog
):
    cache = FilePlanCache(tmp_path)
    data = make_pdf()
    usage = LLMUsage(input_tokens=1200, output_tokens=300)
    first = parse_plan_pdf(data, client=FakeLLM(good_reply(), usage=usage), cache=cache)

    # a rule or the normaliser changed: the parser version goes up
    monkeypatch.setattr(llm_parser, "PARSER_VERSION", "9.9.9")
    silent = FakeLLM()  # has no reply to give: any call would fail the test
    with caplog.at_level(logging.INFO, logger="construtiva.parsing.llm"):
        plan = parse_plan_pdf(data, client=silent, cache=cache)
    assert silent.calls == []
    assert plan["parser"]["parser_version"] == "9.9.9"
    assert plan["levels"] == first["levels"]
    # what the model call cost is kept with the plan; this run cost nothing
    assert (plan["parser"]["input_tokens"], plan["parser"]["attempts"]) == (1200, 1)
    line = next(r.getMessage() for r in caplog.records if "plan parse:" in r.getMessage())
    assert "cache_hit=reply" in line and "input_tokens=0" in line and "attempts=0" in line
    # the rebuilt plan is stored, so the next upload is a plain plan-cache hit
    assert parse_plan_pdf(data, client=FakeLLM(), cache=cache) == plan


def test_the_plan_is_rebuilt_with_todays_rules(tmp_path, monkeypatch):
    cache = FilePlanCache(tmp_path)
    data = make_pdf()
    reply = good_reply()
    reply["levels"][0]["rooms"][0]["name"] = "KIT. 10' X 12'"
    first = parse_plan_pdf(data, client=FakeLLM(reply), cache=cache)
    assert first["levels"][0]["rooms"][0]["boq_type"] == "KITCHEN"

    # the same stored reply, read by a build whose rules type that label differently
    from app.modules.parsing import normalise

    monkeypatch.setattr(llm_parser, "PARSER_VERSION", "9.9.9")
    monkeypatch.setattr(normalise, "resolve_boq_type", lambda name, supplied, area=None: "STORE")
    rebuilt = parse_plan_pdf(data, client=FakeLLM(), cache=cache)
    assert {r["boq_type"] for r in rebuilt["levels"][0]["rooms"] if r["boq_type"]} == {"STORE"}


def test_only_a_new_pdf_prompt_provider_or_model_reaches_the_model(tmp_path, monkeypatch):
    cache = FilePlanCache(tmp_path)
    data = make_pdf()
    parse_plan_pdf(data, client=FakeLLM(good_reply()), cache=cache)

    def calls(pdf: bytes = data, **client) -> int:
        llm = FakeLLM(good_reply(), **client)
        parse_plan_pdf(pdf, client=llm, cache=cache)
        return len(llm.calls)

    assert calls() == 0  # nothing changed
    assert calls(pdf=make_pdf(text="ANOTHER PLAN")) == 1  # another PDF
    assert calls(model="fake-2") == 1  # another model
    other_provider = FakeLLM(good_reply())
    other_provider.provider = "other"
    parse_plan_pdf(data, client=other_provider, cache=cache)
    assert len(other_provider.calls) == 1  # another provider
    monkeypatch.setattr(llm_parser, "prompt_version", lambda: "9.9.9")
    assert calls() == 1  # another prompt
    assert calls() == 0  # and that reply is kept too


def test_reply_cache_key_holds_only_what_decides_the_model_call():
    key = reply_cache_key("abc", "2.2.0", "anthropic", "model-a")
    assert key == "abc.reply.prompt-2.2.0.anthropic.model-a"
    assert PARSER_VERSION not in key and SCHEMA_VERSION not in key.replace("2.2.0", "")
    for other in (
        reply_cache_key("abd", "2.2.0", "anthropic", "model-a"),
        reply_cache_key("abc", "2.2.1", "anthropic", "model-a"),
        reply_cache_key("abc", "2.2.0", "gemini", "model-a"),
        reply_cache_key("abc", "2.2.0", "anthropic", "model-b"),
    ):
        assert other != key


def test_a_stored_reply_that_fails_todays_checks_is_parsed_again(tmp_path, monkeypatch):
    cache = FilePlanCache(tmp_path)
    data = make_pdf()
    parse_plan_pdf(data, client=FakeLLM(good_reply()), cache=cache)
    # corrupt the stored reply the way a stricter future check would see it
    reply_file = next(tmp_path.glob("*.reply.*.json"))
    record = json.loads(reply_file.read_text())
    record["reply"] = broken_reply()
    reply_file.write_text(json.dumps(record))

    monkeypatch.setattr(llm_parser, "PARSER_VERSION", "9.9.9")
    llm = FakeLLM(good_reply())
    plan = parse_plan_pdf(data, client=llm, cache=cache)
    assert len(llm.calls) == 1 and plan["parser"]["parser_version"] == "9.9.9"


def test_unreadable_reply_entries_are_ignored(tmp_path):
    cache = FilePlanCache(tmp_path)
    (tmp_path / "a.reply.json").write_text("{not json")
    (tmp_path / "b.reply.json").write_text(json.dumps({"reply": "not an object"}))
    assert cache.get_reply("a.reply") is None
    assert cache.get_reply("b.reply") is None
    assert cache.get_reply("missing") is None
    cache.put_reply("c.reply", {"reply": {"levels": []}, "attempts": 1})
    assert cache.get_reply("c.reply") == {"reply": {"levels": []}, "attempts": 1}


def test_what_is_sent_to_the_model_is_pinned_to_the_prompt_version():
    """The reply cache trusts the prompt version to stand for everything a model is sent.

    If this fails, the prompt text, the wire schema or the page rendering changed: raise
    `prompt_version` in ai/prompts/parsing/plan_parser.md, then update the fingerprint.
    """
    import hashlib

    prompt_text, version = load_prompt()
    sent = json.dumps(
        [prompt_text, WIRE_JSON_SCHEMA, RENDER_DPI, MAX_IMAGE_SIDE_PX], sort_keys=True
    )
    fingerprint = hashlib.sha256(sent.encode("utf-8")).hexdigest()[:16]
    assert (version, fingerprint) == ("2.2.0", SENT_TO_MODEL_FINGERPRINT)


def test_a_failed_parse_is_not_cached(tmp_path):
    cache = FilePlanCache(tmp_path)
    with pytest.raises(PlanOutputInvalidError):
        parse_plan_pdf(
            make_pdf(), client=FakeLLM(broken_reply(), broken_reply(), broken_reply()), cache=cache
        )
    assert list(tmp_path.glob("*")) == []


def test_a_cached_plan_with_too_few_rooms_is_parsed_again(tmp_path):
    cache = FilePlanCache(tmp_path)
    data = make_pdf()
    sparse = good_reply()
    sparse["levels"][0]["rooms"] = sparse["levels"][0]["rooms"][:1]
    parse_plan_pdf(data, client=FakeLLM(sparse), cache=cache, min_rooms=1)
    llm = FakeLLM(good_reply())
    plan = parse_plan_pdf(data, client=llm, cache=cache, min_rooms=2)
    assert len(llm.calls) == 1 and len(plan["levels"][0]["rooms"]) == 2


def test_corrupt_cache_entry_is_ignored(tmp_path):
    cache = FilePlanCache(tmp_path)
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    assert cache.get("bad") is None
    assert cache.get("missing") is None


# ------------------------------------------------------------- typed provider failures


@pytest.mark.parametrize(
    ("client_error", "parser_error", "code"),
    [
        (LLMAuthenticationError("bad key"), ParserAuthError, "llm_auth_failed"),
        (LLMBillingError("no credit"), ParserBillingError, "llm_billing"),
        (LLMRateLimitError("slow down"), ParserRateLimitedError, "llm_rate_limited"),
        (
            LLMRequestRejectedError("unknown model"),
            ParserRequestRejectedError,
            "llm_request_rejected",
        ),
        (LLMUnavailableError("timeout"), ParserUnavailableError, "llm_unavailable"),
        (LLMNotConfiguredError("no key"), ParserNotConfiguredError, "llm_not_configured"),
    ],
)
def test_provider_failures_become_typed_parse_errors(client_error, parser_error, code):
    llm = FakeLLM(client_error)
    with pytest.raises(parser_error) as caught:
        parse_plan_images(IMAGES, [""], client=llm)
    assert caught.value.code == code
    assert caught.value.details == [str(client_error)]
    assert caught.value.message  # a message a user can be shown
    assert len(llm.calls) == 1  # the parser itself never retries a provider failure


# ---------------------------------------------------------------------- per-parse log


def test_one_log_line_per_parse_with_provider_model_tokens_and_duration(tmp_path, caplog):
    cache = FilePlanCache(tmp_path)
    data = make_pdf(text="CONFIDENTIAL CLIENT NAME")
    llm = FakeLLM(
        broken_reply(), good_reply(), usage=LLMUsage(input_tokens=1200, output_tokens=300)
    )
    with caplog.at_level(logging.INFO, logger="construtiva.parsing.llm"):
        plan = parse_plan_pdf(data, client=llm, cache=cache)
        parse_plan_pdf(data, client=FakeLLM(), cache=cache)

    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("plan parse:")]
    assert len(lines) == 2
    fresh, cached = lines
    for part in (
        "provider=fake",
        "model=fake-1",
        "input_tokens=2400",
        "output_tokens=600",
        "attempts=2",
        "duration_s=",
        "cache_hit=False",
        "outcome=ok",
    ):
        assert part in fresh
    for part in (
        "provider=fake",
        "model=fake-1",
        "input_tokens=0",
        "output_tokens=0",
        "cache_hit=True",
    ):
        assert part in cached
    # the cost of the parse is also kept with the plan
    assert (
        plan["parser"]["input_tokens"],
        plan["parser"]["output_tokens"],
        plan["parser"]["attempts"],
    ) == (2400, 600, 2)
    # nothing from the file is logged
    assert "CONFIDENTIAL" not in caplog.text


def test_a_failed_parse_is_logged_with_its_error_code(caplog):
    with caplog.at_level(logging.INFO, logger="construtiva.parsing.llm"):
        with pytest.raises(ParserBillingError):
            parse_plan_images(IMAGES, [""], client=FakeLLM(LLMBillingError("no credit")))
    assert "outcome=llm_billing" in caplog.text and "cache_hit=False" in caplog.text
