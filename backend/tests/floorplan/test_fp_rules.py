"""Layout rules, the full re-solve, conflicts and options, and the provider-neutral chat."""

import json

import pytest

from app.modules.ai.floorplan.pipeline.edit_engine import edit_plan
from app.modules.ai.floorplan.pipeline.generate import generate_plan
from app.modules.ai.floorplan.pipeline.rules_check import has_door, rule_problems, shared_len
from app.modules.ai.floorplan.schemas.api import EditRequest
from app.modules.ai.floorplan.schemas.brief import Brief, PlotSpec, RoomRequest
from app.modules.ai.floorplan.schemas.rules import Place, Touches, resolve_ref
from app.modules.ai.floorplan.settings import get_settings
from app.modules.ai.floorplan.store import MemoryPlanStore, StoredPlan
from app.modules.ai.llm.client import LLMError

FT = 30.48


class FakeLLM:
    model = "fake-model-1"

    def __init__(self, reply=None):
        self.reply, self.calls = reply, []

    def structured(self, *, system, user, schema, task):
        self.calls.append((task, json.loads(user)))
        if self.reply is None:
            raise LLMError("down")
        return schema.model_validate(self.reply)


def _villa(**kw) -> Brief:
    base = dict(
        plot=PlotSpec(width_cm=round(58 * FT), depth_cm=round(87 * FT), input_unit="ft"),
        bedrooms=2,
        bathrooms=2,
        road_side="south",
        rooms=[
            RoomRequest(type="master_bedroom", count=2, attached_bath=True),
            RoomRequest(type="living"),
            RoomRequest(type="kitchen"),
            RoomRequest(type="bar"),
            RoomRequest(type="puja"),
            RoomRequest(type="pool"),
            RoomRequest(type="garden"),
        ],
    )
    base.update(kw)
    return Brief(**base)


NANDU_RULES = [
    Place(kind="place", room="pool", side="front", text="pool at the front"),
    Place(kind="place", room="garden", side="front", text="garden at the front"),
    Touches(
        kind="touches",
        room="pool",
        others=["kitchen", "living", "bar"],
        door=True,
        text="pool touches the kitchen, living and bar, each with a door onto it",
    ),
]


@pytest.fixture(scope="module")
def nandu_like():
    """The request the old chat refused, as rules in the brief (no AI)."""
    res = generate_plan(_villa(rules=NANDU_RULES), llm=None, solver_time_s=12)
    assert res.ok, res.message
    return res


@pytest.mark.site_rules
def test_pool_touches_three_rooms_with_a_door_each(nandu_like) -> None:
    plan, program = nandu_like.plan, nandu_like.program
    pool = next(r for r in plan.rooms if r.type == "pool")
    for t in ("kitchen", "living", "bar"):
        room = next(r for r in plan.rooms if r.type == t)
        assert shared_len(pool, room) >= 90, t
        assert has_door(plan, pool.id, room.id), t
    assert rule_problems(plan, program) == []
    road = plan.plot.depth  # road on the south: front = larger y
    for t in ("pool", "garden"):
        r = next(r for r in plan.rooms if r.type == t)
        assert r.y + r.h / 2 >= road / 2, t


def test_a_broken_rule_is_reported(nandu_like) -> None:
    plan, program = nandu_like.plan, nandu_like.program
    puja = next(r.id for r in plan.rooms if r.type == "puja")
    pool = next(r.id for r in plan.rooms if r.type == "pool")
    bad = program.model_copy(
        update={"rules": [*program.rules, Touches(kind="touches", room=pool, others=[puja])]}
    )
    if shared_len(plan.room(pool), plan.room(puja)) < 90:
        assert rule_problems(plan, bad)


def test_room_references_resolve_by_id_type_and_label(nandu_like) -> None:
    rooms = nandu_like.plan.rooms
    assert resolve_ref("kitchen", rooms) == next(r.id for r in rooms if r.type == "kitchen")
    assert resolve_ref("BAR", rooms) == next(r.id for r in rooms if r.type == "bar")
    assert resolve_ref("no such room", rooms) is None


@pytest.fixture
def quick_resolve(monkeypatch):
    monkeypatch.setattr(get_settings(), "full_resolve_s", 14.0)


def test_chat_rules_re_solve_the_plan(quick_resolve) -> None:
    base = generate_plan(_villa(), llm=None, solver_time_s=8)
    assert base.ok
    plan, program = base.plan, base.program
    ids = {r.type: r.id for r in plan.rooms}
    llm = FakeLLM(
        {
            "ops": [
                {
                    "op": "add_rules",
                    "rules": [
                        {
                            "kind": "touches",
                            "room": ids["pool"],
                            "others": [ids["kitchen"], ids["living"], ids["bar"]],
                            "door": True,
                            "text": "pool next to kitchen, living and bar with doors",
                        }
                    ],
                },
                {"op": "resolve", "reason": "break the plan"},
            ]
        }
    )
    res = edit_plan(plan, program, "break the plan and do as I asked", llm)
    assert res.ok and res.resolved, res.message
    assert "not supported" not in " ".join(res.summary + res.warnings).lower()
    assert rule_problems(res.plan, res.program) == []
    assert len(res.program.rules) == 1


def test_conflicting_rules_are_named_and_two_layouts_offered(quick_resolve) -> None:
    base = generate_plan(_villa(), llm=None, solver_time_s=8)
    plan, program = base.plan, base.program
    pool = next(r.id for r in plan.rooms if r.type == "pool")
    llm = FakeLLM(
        {
            "ops": [
                {
                    "op": "add_rules",
                    "rules": [
                        {"kind": "place", "room": pool, "side": "front", "text": "pool at front"},
                        {"kind": "place", "room": pool, "side": "rear", "text": "pool at rear"},
                    ],
                }
            ]
        }
    )
    res = edit_plan(plan, program, "pool at the front and at the back", llm)
    assert res.status == "impossible"
    assert "pool at front" in res.message and "pool at rear" in res.message
    assert len(res.options) == 2 and "option 1" in res.message
    assert res.plan is plan  # nothing changed


def test_choosing_an_offered_layout_and_recording_the_model(quick_resolve) -> None:
    from app.modules.ai.floorplan import service

    base = generate_plan(_villa(), llm=None, solver_time_s=8)
    store = MemoryPlanStore()
    sp = StoredPlan(
        id="p1", owner_id="u", name="Villa", plan=base.plan, program=base.program, model="m0"
    )
    store.create(sp)
    pool = next(r.id for r in base.plan.rooms if r.type == "pool")
    conflict = FakeLLM(
        {
            "ops": [
                {
                    "op": "add_rules",
                    "rules": [
                        {"kind": "place", "room": pool, "side": "front", "text": "front"},
                        {"kind": "place", "room": pool, "side": "rear", "text": "rear"},
                    ],
                }
            ]
        }
    )
    service.edit(sp, EditRequest(message="pool front and rear"), conflict, store)
    assert len(sp.options) == 2 and sp.version == 1
    pick = FakeLLM({"ops": [{"op": "choose_option", "n": 2}]})
    out = service.edit(sp, EditRequest(message="use option 2"), pick, store)
    assert out.status == "ok" and sp.version == 2
    assert sp.model == "fake-model-1" and sp.history[-1]["model"] == "m0"
    assert sp.options == []
    assert "Total area" in sp.messages[-1]["text"]


def test_neutral_adapter_corrects_invalid_output_once() -> None:
    from app.modules.ai.floorplan.pipeline.edit_engine import EditInterpretation
    from app.modules.ai.llm.neutral import NeutralLLM

    class Client:
        provider, model, last_usage = "fake", "fake-strong", None

        def __init__(self):
            self.replies = [{"ops": [{"op": "nope"}]}, {"ops": []}]
            self.texts = []

        def generate_json(self, *, system_prompt, images, text, json_schema=None):
            self.texts.append(text)
            return self.replies.pop(0)

    client = Client()
    llm = NeutralLLM(client)
    out = llm.structured(system="s", user="{}", schema=EditInterpretation, task="edit_ops")
    assert out.ops == [] and llm.model == "fake-strong"
    assert "invalid" in client.texts[1]
