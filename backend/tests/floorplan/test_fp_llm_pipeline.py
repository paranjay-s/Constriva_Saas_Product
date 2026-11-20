"""Phase 4: LLM wrapper, brief parser, feasibility, room program, retry loop.

All tests use a fake LLM or a mocked HTTP transport; no network. The one live test runs
only with FLOORPLAN_LIVE_LLM=1 and a configured API key.
"""

import json
import os

import httpx
import pytest

from app.modules.ai.floorplan.pipeline import generate as gen_mod
from app.modules.ai.floorplan.pipeline.brief_parser import parse_brief
from app.modules.ai.floorplan.pipeline.feasibility import check_feasibility
from app.modules.ai.floorplan.pipeline.generate import generate_plan
from app.modules.ai.floorplan.pipeline.layout.engine import LayoutResult
from app.modules.ai.floorplan.pipeline.requirements import expand_rooms
from app.modules.ai.floorplan.pipeline.room_program import ProgramDraft, build_program
from app.modules.ai.floorplan.pipeline.validator import Issue, ValidationReport
from app.modules.ai.floorplan.render import render_svg
from app.modules.ai.floorplan.schemas.brief import BriefForm, TextBrief
from app.modules.ai.llm.client import GeminiClient, LLMError, get_llm


class FakeLLM:
    """Returns canned objects per task and records what it was asked."""

    def __init__(self, responses: dict, fail: set[str] | None = None) -> None:
        self.responses = responses
        self.fail = fail or set()
        self.calls: list[tuple[str, dict]] = []

    def structured(self, *, system, user, schema, task):
        self.calls.append((task, json.loads(user)))
        if task in self.fail:
            raise LLMError("boom")
        r = self.responses[task]
        r = r(json.loads(user)) if callable(r) else r
        return schema.model_validate(r) if isinstance(r, dict) else r


def _text(**kw) -> dict:
    return TextBrief(**kw).model_dump()


# ------------------------------------------------------------------ wrapper


def _gemini(handler) -> GeminiClient:
    return GeminiClient(
        model="test-model",
        temperature=0.1,
        timeout_s=5,
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        max_busy_retries=0,
    )


def _reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


def test_wrapper_validates_and_sends_key_in_header() -> None:
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["key"] = req.headers.get("x-goog-api-key")
        body = json.loads(req.content)
        seen["temp"] = body["generationConfig"]["temperature"]
        return _reply('```json\n{"bedrooms": 3, "road_side": "east"}\n```')

    out = _gemini(handler).structured(system="s", user="u", schema=TextBrief, task="t")
    assert out.bedrooms == 3 and out.road_side == "east"
    assert seen["key"] == "test-key" and "test-key" not in seen["url"]
    assert seen["temp"] == 0.1


def test_wrapper_retries_once_with_validation_errors() -> None:
    bodies = []

    def handler(req: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(req.content))
        return _reply('{"bedrooms": -2}' if len(bodies) == 1 else '{"bedrooms": 2}')

    out = _gemini(handler).structured(system="s", user="u", schema=TextBrief, task="t")
    assert out.bedrooms == 2
    assert len(bodies) == 2
    assert "invalid" in bodies[1]["contents"][-1]["parts"][0]["text"]


def test_wrapper_raises_after_two_invalid_replies() -> None:
    client = _gemini(lambda req: _reply("not json"))
    with pytest.raises(LLMError):
        client.structured(system="s", user="u", schema=TextBrief, task="t")


@pytest.fixture
def clean_cooldown():
    from app.modules.ai.llm import client as client_mod

    client_mod._unavailable_until.clear()
    yield client_mod
    client_mod._unavailable_until.clear()


def test_wrapper_falls_back_when_main_model_is_gone_then_skips_it(clean_cooldown) -> None:
    hits: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        model = "main" if "/main:" in str(req.url) else "backup"
        hits.append(model)
        body = json.loads(req.content)
        if model == "main":
            return httpx.Response(404, json={"error": {"message": "retired"}})
        assert "thinkingConfig" not in body["generationConfig"]  # only sent to the main model
        return _reply('{"bedrooms": 1}')

    client = GeminiClient(
        model="main",
        fallback_model="backup",
        temperature=0.1,
        timeout_s=5,
        api_key="k",
        transport=httpx.MockTransport(handler),
        max_busy_retries=0,
        thinking="low",
    )
    assert client.structured(system="s", user="u", schema=TextBrief, task="t").bedrooms == 1
    assert client.structured(system="s", user="u", schema=TextBrief, task="t").bedrooms == 1
    assert hits == ["main", "backup", "backup"]  # second call skips the failing main model


def test_wrapper_falls_back_on_timeout(clean_cooldown) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if "/main:" in str(req.url):
            raise httpx.ReadTimeout("slow", request=req)
        return _reply('{"bedrooms": 2}')

    client = GeminiClient(
        model="main",
        fallback_model="backup",
        temperature=0.1,
        timeout_s=5,
        api_key="k",
        transport=httpx.MockTransport(handler),
        max_busy_retries=0,
    )
    assert client.structured(system="s", user="u", schema=TextBrief, task="t").bedrooms == 2


def test_wrapper_does_not_mask_bad_requests(clean_cooldown) -> None:
    client = GeminiClient(
        model="main",
        fallback_model="backup",
        temperature=0.1,
        timeout_s=5,
        api_key="k",
        transport=httpx.MockTransport(lambda req: httpx.Response(400, json={})),
        max_busy_retries=0,
    )
    with pytest.raises(LLMError, match="rejected"):
        client.structured(system="s", user="u", schema=TextBrief, task="t")


def test_wrapper_without_key_raises_cleanly() -> None:
    client = GeminiClient(model="m", temperature=0.1, timeout_s=1, api_key="")
    with pytest.raises(LLMError, match="not configured"):
        client.structured(system="s", user="u", schema=TextBrief, task="t")


# -------------------------------------------------------------- brief parser


def test_form_only_brief() -> None:
    pr = parse_brief(
        BriefForm(plot_width=40, plot_depth=50, unit="ft", bedrooms=2, road_side="north")
    )
    b = pr.brief
    assert (b.plot.width_cm, b.plot.depth_cm) == (1219, 1524)
    assert b.bedrooms == 2 and b.road_side == "north"
    assert "bathrooms" in b.unknowns and "purpose" in b.unknowns
    assert pr.ready and pr.warnings == []


def test_prompt_wins_and_conflict_is_reported() -> None:
    llm = FakeLLM({"brief_parser": _text(bedrooms=3, rooms=[{"type": "bedroom", "count": 3}])})
    pr = parse_brief(
        BriefForm(plot_width=40, plot_depth=60, bedrooms=2, prompt="3 BHK please"), llm
    )
    assert pr.brief.bedrooms == 3
    assert sum(r.count for r in pr.brief.rooms if r.type == "bedroom") == 3
    assert [(c.field, c.form_value, c.text_value) for c in pr.brief.conflicts] == [
        ("bedrooms", "2", "3")
    ]


def test_text_fills_what_the_form_left_empty() -> None:
    llm = FakeLLM(
        {
            "brief_parser": _text(
                plot_width=30,
                plot_depth=45,
                plot_unit="ft",
                bedrooms=3,
                bathrooms=2,
                road_side="east",
                rooms=[
                    {"type": "master_bedroom", "count": 1, "attached_bath": True},
                    {"type": "bedroom", "count": 2},
                    {"type": "dining"},
                ],
                preferences=[
                    {
                        "kind": "adjacent",
                        "a": "kitchen",
                        "b": "dining",
                        "text": "kitchen next to dining",
                    }
                ],
            )
        }
    )
    pr = parse_brief(BriefForm(prompt="3BHK on 30x45 ft, east facing, kitchen next to dining"), llm)
    b = pr.brief
    assert b.bedrooms == 3 and b.road_side == "east" and b.plot.width_cm == 914
    assert any(r.type == "master_bedroom" and r.attached_bath for r in b.rooms)
    assert b.preferences[0].b == "dining"
    assert pr.ready and b.conflicts == []


def test_area_only_assumes_shape_and_says_so() -> None:
    pr = parse_brief(BriefForm(plot_area=1200, unit="ft", bedrooms=2))
    b = pr.brief
    assert b.plot.shape_assumed
    assert abs(b.plot.width_cm * b.plot.depth_cm / 10_000 - 111.5) < 1
    assert any("2:3" in a for a in b.assumptions)


def test_missing_plot_blocks_generation() -> None:
    pr = parse_brief(BriefForm(bedrooms=2))
    assert not pr.ready and "plot size" in pr.missing[0]
    assert generate_plan(pr.brief).status == "incomplete"


def test_llm_failure_falls_back_to_form_with_warning() -> None:
    llm = FakeLLM({}, fail={"brief_parser"})
    pr = parse_brief(BriefForm(plot_width=40, plot_depth=50, bedrooms=2, prompt="something"), llm)
    assert pr.ready and pr.brief.bedrooms == 2
    assert pr.warnings and "only the form values" in pr.warnings[0]


def test_unsupported_requests_are_reported() -> None:
    llm = FakeLLM({"brief_parser": _text(unsupported=["second floor"])})
    pr = parse_brief(
        BriefForm(plot_width=40, plot_depth=50, bedrooms=2, prompt="with a second floor"), llm
    )
    assert any("second floor" in w for w in pr.warnings)


def test_names_come_only_from_user_input() -> None:
    pr = parse_brief(BriefForm(plot_width=40, plot_depth=50, bedrooms=2))
    assert pr.brief.project_name == "" and pr.brief.owner_name == ""
    llm = FakeLLM({"brief_parser": _text(owner_name="A. Client")})
    pr = parse_brief(
        BriefForm(plot_width=40, plot_depth=50, bedrooms=2, prompt="for A. Client"), llm
    )
    assert pr.brief.owner_name == "A. Client"


# --------------------------------------------------------- rooms / feasibility


def test_expand_rooms_ids_and_attachments() -> None:
    llm = FakeLLM(
        {
            "brief_parser": _text(
                rooms=[
                    {"type": "master_bedroom", "attached_bath": True, "dress_room": True},
                    {"type": "bedroom", "count": 2},
                ]
            )
        }
    )
    pr = parse_brief(
        BriefForm(plot_width=50, plot_depth=60, bedrooms=3, bathrooms=2, prompt="x"), llm
    )
    rooms, _ = expand_rooms(pr.brief)
    ids = {r.id: r for r in rooms}
    assert ids["bed_1"].type == "master_bedroom"
    assert ids["bath_1"].attached_to == "bed_1" and ids["dress_1"].attached_to == "bed_1"
    assert "bath_c1" in ids and "bath_c2" not in ids  # 2 bathrooms = 1 attached + 1 common
    assert "lobby_1" in ids  # 3 bedrooms get a lobby


def test_feasibility_rejects_with_reason_and_options() -> None:
    pr = parse_brief(BriefForm(plot_width=7, plot_depth=8, unit="m", bedrooms=3, bathrooms=3))
    feas = check_feasibility(pr.brief)
    assert not feas.ok
    assert "need about" in feas.message and "56 m2" in feas.message
    assert any(o.startswith("Reduce to") for o in feas.options)
    assert any("larger plot" in o for o in feas.options)
    # the feasibility check still explains the problem, but a plan is always made (A1):
    # the relaxation ladder shrinks the rooms and the notes say so
    res = generate_plan(pr.brief)
    assert res.status == "ok" and res.plan is not None and res.relax_step
    assert feas.message in res.warnings


def test_feasibility_rejects_too_narrow_plot() -> None:
    pr = parse_brief(BriefForm(plot_width=8, plot_depth=200, unit="ft", bedrooms=1))
    feas = check_feasibility(pr.brief)
    assert not feas.ok and "too narrow" in feas.message


# --------------------------------------------------------------- room program


def _brief_3bed():
    llm = FakeLLM(
        {
            "brief_parser": _text(
                rooms=[
                    {"type": "master_bedroom", "attached_bath": True},
                    {"type": "bedroom", "count": 2},
                    {"type": "dining"},
                ],
                preferences=[{"kind": "adjacent", "a": "kitchen", "b": "dining"}],
            )
        }
    )
    return parse_brief(
        BriefForm(
            plot_width=12,
            plot_depth=15,
            unit="m",
            bedrooms=3,
            bathrooms=2,
            road_side="south",
            prompt="x",
        ),
        llm,
    ).brief


def test_program_uses_llm_sizes_but_keeps_ids_and_minimums() -> None:
    brief = _brief_3bed()

    def draft(payload):
        rooms = [
            {"id": r["id"], "target_area_m2": 1.0 if r["id"] == "bed_2" else 14.0}
            for r in payload["rooms"]
        ]
        rooms.append({"id": "invented_9", "target_area_m2": 50})
        return {
            "rooms": rooms,
            "adjacency": [
                {"a": "living_1", "b": "dining_1", "weight": 4},
                {"a": "ghost", "b": "living_1"},
            ],
        }

    llm = FakeLLM({"room_program": draft})
    program, _ = build_program(brief, llm)
    ids = {r.id for r in program.rooms}
    assert "invented_9" not in ids and {"bed_1", "bath_1", "bed_2", "bath_c1"} <= ids
    bed2 = next(r for r in program.rooms if r.id == "bed_2")
    assert bed2.target_area_m2 >= 9.5  # LLM's 1 m2 lifted to the minimum
    adj = {(a.a, a.b) for a in program.adjacency}
    assert ("dining_1", "kitchen_1") in adj  # the person's preference, independent of the LLM
    assert all("ghost" not in pair for pair in adj)
    bath1 = next(r for r in program.rooms if r.id == "bath_1")
    assert bath1.attached_to == "bed_1"  # attachments come from code, not the LLM


def test_program_without_llm_uses_typical_sizes_scaled_to_plot() -> None:
    program, notes = build_program(_brief_3bed(), None)
    fixed = sum(r.target_area_m2 for r in program.rooms if r.type not in ("lobby", "garden"))
    assert 0.6 * 180 <= fixed <= 0.9 * 180


def test_program_llm_failure_degrades_with_warning() -> None:
    program, notes = build_program(_brief_3bed(), FakeLLM({}, fail={"room_program"}))
    assert program.rooms and any("typical room sizes" in n for n in notes)


def test_feedback_is_sent_back_on_retry() -> None:
    brief = _brief_3bed()
    llm = FakeLLM(
        {
            "room_program": lambda p: ProgramDraft(
                rooms=[{"id": r["id"], "target_area_m2": 10} for r in p["rooms"]]
            ).model_dump()
        }
    )
    first, _ = build_program(brief, llm)
    build_program(brief, llm, feedback=["MIN_SIDE: bed_2 short side is 250 cm"], previous=first)
    task, payload = llm.calls[-1]
    assert task == "room_program"
    assert payload["layout_errors"] == ["MIN_SIDE: bed_2 short side is 250 cm"]
    assert "previous_targets" in payload


# ------------------------------------------------------------- orchestrator


def test_retry_loop_feeds_errors_and_stops_at_max(monkeypatch) -> None:
    brief = _brief_3bed()
    calls = []
    report = ValidationReport(
        errors=[Issue("OVERLAP", "bed_1 and bed_2 overlap by 1.00 m2", ("bed_1", "bed_2"))]
    )

    def fake_layout(program, plot, meta, plan_id, **kw):
        calls.append(program)
        return LayoutResult(None, report, "solver", ["solver: fail"])

    monkeypatch.setattr(gen_mod, "generate_layout", fake_layout)
    llm = FakeLLM(
        {
            "room_program": lambda p: {
                "rooms": [{"id": r["id"], "target_area_m2": 10} for r in p["rooms"]]
            }
        }
    )
    res = generate_plan(brief, llm=llm, max_attempts=3)
    # three attempts with feedback, then the relaxation ladder delivers a plan anyway
    assert res.status == "ok" and res.plan is not None and res.relax_step
    # attempt 1 tries with daylight rules for habitable rooms first, then without
    assert len(calls) == 4 and any(r.kind == "daylight" for r in calls[0].rules)
    feedback_calls = [p for t, p in llm.calls if t == "room_program" and "layout_errors" in p]
    assert len(feedback_calls) == 2
    assert feedback_calls[0]["layout_errors"] == ["OVERLAP: bed_1 and bed_2 overlap by 1.00 m2"]


def test_end_to_end_with_fake_llm_produces_valid_plan() -> None:
    llm = FakeLLM(
        {
            "brief_parser": _text(
                rooms=[
                    {"type": "master_bedroom", "attached_bath": True},
                    {"type": "bedroom"},
                    {"type": "dining"},
                    {"type": "foyer"},
                    {"type": "garden"},
                ]
            ),
            "room_program": lambda p: {
                "rooms": [
                    {"id": r["id"], "target_area_m2": max(r["min_area_m2"], 9)} for r in p["rooms"]
                ]
            },
        }
    )
    form = BriefForm(
        plot_width=40,
        plot_depth=36,
        unit="ft",
        bedrooms=2,
        bathrooms=2,
        road_side="south",
        project_name="Proj One",
        prompt="2 bed with master ensuite, dining, foyer, garden",
    )
    pr = parse_brief(form, llm)
    res = generate_plan(pr.brief, llm=llm)
    assert res.ok, (res.message, res.attempts)
    assert res.plan.meta.project == "Proj One" and res.plan.meta.owner == ""
    assert res.plan.meta.unit_display == "ft"
    assert any({d.from_room, d.to_room} == {"bed_1", "bath_1"} for d in res.plan.doors)


def test_two_different_prompts_produce_different_plans() -> None:
    def run(prompt_rooms, bedrooms):
        llm = FakeLLM(
            {
                "brief_parser": _text(rooms=prompt_rooms),
                "room_program": lambda p: {
                    "rooms": [
                        {"id": r["id"], "target_area_m2": max(r["min_area_m2"], 10)}
                        for r in p["rooms"]
                    ]
                },
            }
        )
        pr = parse_brief(
            BriefForm(
                plot_width=12,
                plot_depth=13,
                unit="m",
                bedrooms=bedrooms,
                road_side="south",
                prompt="x",
            ),
            llm,
        )
        res = generate_plan(pr.brief, llm=llm)
        assert res.ok, res.message
        return res.plan

    a = run([{"type": "dining"}], 2)
    b = run([{"type": "study"}, {"type": "parking"}], 3)
    assert {r.type for r in a.rooms} != {r.type for r in b.rooms}
    assert render_svg(a) != render_svg(b)


@pytest.mark.skipif(os.environ.get("FLOORPLAN_LIVE_LLM") != "1", reason="live LLM test is opt-in")
def test_live_llm_brief_and_plan() -> None:
    llm = get_llm()
    pr = parse_brief(
        BriefForm(
            plot_width=40,
            plot_depth=50,
            unit="ft",
            road_side="east",
            prompt="3 BHK with an attached bath in the master bedroom, kitchen next to dining",
        ),
        llm,
    )
    assert pr.brief.bedrooms == 3
    res = generate_plan(pr.brief, llm=llm)
    assert res.ok, res.message


# ------------------------------------------------------- sizing and bathroom rules


def test_bedrooms_without_attached_bath_always_get_a_common_bath() -> None:
    llm = FakeLLM(
        {
            "brief_parser": _text(
                bathrooms=1,
                rooms=[
                    {"type": "master_bedroom", "attached_bath": True},
                    {"type": "bedroom", "count": 2},
                ],
            )
        }
    )
    pr = parse_brief(BriefForm(plot_width=40, plot_depth=50, prompt="3 BHK"), llm)
    rooms, notes = expand_rooms(pr.brief)
    ids = {r.id for r in rooms}
    assert {"bath_1", "bath_c1"} <= ids
    assert any("common bathroom was added" in n for n in notes)


def test_form_bathroom_count_is_dropped_when_prompt_overrides_bedrooms() -> None:
    llm = FakeLLM(
        {
            "brief_parser": _text(
                bedrooms=6,
                rooms=[{"type": "bedroom", "count": 6, "attached_bath": True}],
            )
        }
    )
    form = BriefForm(plot_width=50, plot_depth=50, bedrooms=4, bathrooms=4, prompt="6 bed")
    pr = parse_brief(form, llm)
    assert pr.brief.bedrooms == 6 and pr.brief.bathrooms is None
    assert ("bedrooms", "4", "6") in [
        (c.field, c.form_value, c.text_value) for c in pr.brief.conflicts
    ]
    assert any("recalculated for 6" in a for a in pr.brief.assumptions)
    rooms, _ = expand_rooms(pr.brief)
    assert sum(r.type == "bath" for r in rooms) == 6  # one attached bath per bedroom


def test_prompt_plot_size_wins_over_form() -> None:
    llm = FakeLLM({"brief_parser": _text(plot_width=30, plot_depth=40, plot_unit="ft")})
    pr = parse_brief(BriefForm(plot_width=40, plot_depth=50, unit="ft", prompt="30x40"), llm)
    assert pr.brief.plot.width_cm == round(30 * 30.48)
    assert [c.field for c in pr.brief.conflicts] == ["plot size"]


@pytest.mark.parametrize("extra", ["parking", "courtyard"])
def test_open_areas_do_not_swallow_the_plot(extra: str) -> None:
    llm = FakeLLM(
        {
            "brief_parser": _text(
                rooms=[
                    {"type": "master_bedroom", "attached_bath": True},
                    {"type": "bedroom", "count": 2},
                    {"type": "dining"},
                    {"type": extra},
                ]
            )
        }
    )
    form = BriefForm(plot_width=40, plot_depth=50, unit="ft", road_side="east", prompt="x")
    pr = parse_brief(form, llm)
    res = generate_plan(pr.brief, llm=None)
    assert res.ok, (res.message, res.attempts)
    plot_m2 = res.plan.plot.width * res.plan.plot.depth / 10_000
    open_room = next(r for r in res.plan.rooms if r.type == extra)
    assert open_room.area_m2 <= (30 if extra == "parking" else 0.25 * plot_m2)
    beds = [r for r in res.plan.rooms if r.type in ("bedroom", "master_bedroom")]
    assert min(r.area_m2 for r in beds) >= 11  # rooms got the space, not the open area


def test_room_named_only_in_a_wish_is_added() -> None:
    """'kitchen next to dining' / 'utility near the kitchen' must give a dining / utility."""
    llm = FakeLLM(
        {
            "brief_parser": _text(
                preferences=[
                    {"kind": "adjacent", "a": "kitchen", "b": "dining"},
                    {"kind": "near", "a": "utility", "b": "kitchen"},
                    {"kind": "away_from", "a": "store", "b": "living"},
                ]
            )
        }
    )
    pr = parse_brief(
        BriefForm(plot_width=40, plot_depth=50, bedrooms=2, prompt="kitchen next to dining"), llm
    )
    types = [r.type for r in pr.brief.rooms]
    assert "dining" in types and "utility" in types
    assert types.count("kitchen") == 1
    assert "store" not in types  # "away from" does not ask for the room
    assert any("dining" in a for a in pr.brief.assumptions)
