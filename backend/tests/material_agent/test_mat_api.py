"""Material Finder end to end over HTTP (fake vision model, memory store, fake parser)."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.core.security import AuthenticatedUser, get_current_user
from app.main import app
from app.modules.ai.material_agent import service
from app.modules.ai.material_agent.jobs import JobManager
from app.modules.ai.material_agent.plan_upload import PlanUploadError
from app.modules.ai.material_agent.projects import MemoryProjectSource, find_project
from app.modules.ai.material_agent.router import get_deps
from app.modules.ai.material_agent.store import MemorySessionStore
from tests.material_agent.conftest import FakeVision, jpeg_bytes, plan_json

BASE = "/api/v1/ai/material-analysis"
KITCHEN_PLAN = plan_json(
    [
        ("Kitchen", 0, 0, 10, 8),
        ("Living", 10, 0, 16, 14),
        ("Bedroom 1", 0, 8, 10, 12),
        ("Bedroom 2", 26, 0, 12, 12),
    ]
)


class Env:
    def __init__(self) -> None:
        self.user = "user-a"
        self.vision = FakeVision()
        self.projects = MemoryProjectSource()
        self.parsed: list[str] = []
        self.parse_result: dict | Exception = KITCHEN_PLAN
        self.store = MemorySessionStore()
        self.jobs = JobManager()

    def parser(self, data: bytes, mime: str) -> dict:
        self.parsed.append(mime)
        if isinstance(self.parse_result, Exception):
            raise self.parse_result
        return self.parse_result

    def deps(self) -> service.Deps:
        return service.Deps(
            store=self.store,
            jobs=self.jobs,
            projects=self.projects,
            vision_llm=self.vision,
            text_llm=None,  # keyword reader + template explanation: deterministic
            plan_parser=self.parser,
            vision_model="fake",
            store_files=False,
        )


@pytest.fixture
def api():
    env = Env()
    app.dependency_overrides[get_deps] = env.deps
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        user_id=env.user, email="x@example.test"
    )
    with TestClient(app) as client:
        yield client, env
    app.dependency_overrides.clear()


def _wait(client: TestClient, job_id: str, timeout: float = 20) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        st = client.get(f"{BASE}/jobs/{job_id}").json()
        if st["status"] in ("done", "failed"):
            return st
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def _analyse(client: TestClient, space: dict | None = None, **form) -> dict:
    data = {"focus_areas": "wall", "focus": "TV wall", **form}
    if space:
        data["space"] = json.dumps(space)
    res = client.post(
        f"{BASE}", files=[("images", ("tv.jpg", jpeg_bytes(), "image/jpeg"))], data=data
    )
    assert res.status_code == 202, res.text
    body = res.json()
    st = _wait(client, body["job_id"])
    assert st["status"] == "done", st
    stages = [e["stage"] for e in st["events"]]
    assert stages[:2] == ["queued", "uploading"] and stages[-1] == "done"
    return client.get(f"{BASE}/{body['report_id']}").json()


def _chat(client: TestClient, rid: str, message: str, file: tuple | None = None) -> dict:
    files = {"file": file} if file else None
    res = client.post(f"{BASE}/{rid}/chat", data={"message": message}, files=files)
    assert res.status_code == 200, res.text
    return res.json()


def _line(view: dict, material_word: str, where: str = "") -> dict:
    return next(
        ln
        for ln in view["report"]["lines"]
        if material_word in ln["material"].lower() and where in ln["application"].lower()
    )


def test_tv_wall_worked_example_over_http(api):
    client, env = api
    view = _analyse(client, {"kind": "wall", "length": 12, "height": 10, "label": "TV wall"})
    assert view["focus"] == "wall, TV wall"
    veneer, marble = _line(view, "veneer"), _line(view, "marble")
    assert (veneer["total_qty"], veneer["buy_qty"]) == (92.4, 3)
    assert marble["total_qty"] == 39.6
    assert view["report"]["note"].startswith("Quantities are planning estimates")
    assert "92.4" in view["report"]["explanation"]
    # images were sent downscaled as JPEG, once
    assert env.vision.calls == 1 and env.vision.last_images[0][1] == "image/jpeg"


def test_same_photo_and_focus_uses_the_cache(api):
    client, env = api
    _analyse(client, {"kind": "wall", "length": 12, "height": 10})
    _analyse(client, {"kind": "wall", "length": 14, "height": 10})
    assert env.vision.calls == 1


def test_recalculate_changes_numbers_without_vision_call(api):
    client, env = api
    view = _analyse(client, {"kind": "wall", "length": 12, "height": 10})
    veneer_id = _line(view, "veneer")["material_id"]
    res = client.post(
        f"{BASE}/{view['id']}/recalculate",
        json={
            "space": {"kind": "wall", "length": 14, "height": 10},
            "overrides": {"wastage_pct": {veneer_id: 15}},
        },
    )
    assert res.status_code == 200, res.text
    v2 = res.json()
    assert _line(v2, "veneer")["total_qty"] == 112.7  # 140 x 0.7 = 98 -> +15 %
    assert _line(v2, "marble")["total_qty"] == 46.2  # 140 x 0.3 = 42 -> +10 %
    assert v2["report"]["version"] == 2
    assert env.vision.calls == 1


def test_follow_up_with_uploaded_plan_never_calls_vision_again(api):
    client, env = api
    env.projects.add("user-a", "p1", "Green Villa", plan_json([("Kitchen", 0, 0, 12, 9)]))
    saved_before = json.dumps(env.projects.plans, sort_keys=True)
    view = _analyse(client, {"kind": "wall", "length": 12, "height": 10})
    rid = view["id"]
    r1 = _chat(client, rid, "how much marble for the kitchen platform?")
    assert r1["status"] == "needs_input" and "attach a floor plan" in r1["message"]
    r2 = _chat(client, rid, "here is my plan", ("plan.pdf", b"%PDF-1.4 fake", "application/pdf"))
    assert r2["status"] == "working" and r2["job_id"]
    _wait(client, r2["job_id"])
    v = client.get(f"{BASE}/{rid}").json()
    assert v["uploaded_plan_name"] == "plan.pdf"
    assert v["pending_question"]["options"] == [
        "One wall",
        "L-shape",
        "U-shape",
        "Parallel",
        "Island",
    ]
    r3 = _chat(client, rid, "L-shape")
    assert r3["status"] == "ok", r3
    line = _line(r3["session"], "marble", "platform")
    assert (line["surface_sqft"], line["total_qty"]) == (32.0, 35.2)
    assert "corner counted once" in json.dumps(line["breakdown"])
    assert "35.2" in r3["message"]
    assert env.parsed == ["application/pdf"]
    assert env.vision.calls == 1  # the follow-up did not look at the photo again
    assert json.dumps(env.projects.plans, sort_keys=True) == saved_before  # saved plan untouched


def test_follow_up_with_own_project(api):
    client, env = api
    env.projects.add("user-a", "p1", "Green Villa", KITCHEN_PLAN)
    env.projects.add("user-b", "p2", "Sea View", KITCHEN_PLAN)
    view = _analyse(client, {"kind": "wall", "length": 12, "height": 10})
    rid = view["id"]
    other = _chat(client, rid, "use project Sea View")
    assert (
        other["status"] == "not_found"
        and "Green Villa" in other["message"]
        and "Sea View" not in other["options"]
    )
    ok = _chat(client, rid, "use project green villa")
    assert ok["status"] == "ok" and "Kitchen" in ok["message"]
    r = _chat(client, rid, "how much marble for the kitchen platform, L-shape")
    assert r["status"] == "ok"
    assert _line(r["session"], "marble", "platform")["total_qty"] == 35.2
    amb = _chat(client, rid, "how much veneer for the bedroom floor")
    assert amb["status"] == "needs_input" and len(amb["options"]) == 2
    pick = _chat(client, rid, amb["options"][1])
    assert pick["status"] == "ok" and "Bedroom 2" in pick["message"]


def test_money_questions_get_the_fixed_answer(api):
    client, _ = api
    view = _analyse(client, {"kind": "wall", "length": 12, "height": 10})
    for q in ("how much will it cost?", "what is the price of this marble", "fits my budget?"):
        r = _chat(client, view["id"], q)
        assert r["status"] == "ok" and "quantities only" in r["message"]
    assert "how much marble" not in r["message"]


def test_material_not_in_photo_and_unreadable_plan(api):
    client, env = api
    view = _analyse(client, {"kind": "wall", "length": 12, "height": 10})
    r = _chat(client, view["id"], "how much granite for the kitchen floor")
    assert r["status"] == "not_found" and "Statuario marble" in r["message"]
    env.parse_result = PlanUploadError("I could not read rooms from that plan.")
    up = _chat(client, view["id"], "", ("p.png", jpeg_bytes(), "image/png"))
    _wait(client, up["job_id"])
    v = client.get(f"{BASE}/{view['id']}").json()
    assert v["messages"][-1]["status"] == "failed" and v["uploaded_plan_name"] is None


def test_vision_failure_is_reported_never_invented(api):
    client, env = api
    env.vision = FakeVision(fail=True)
    res = client.post(
        f"{BASE}",
        files=[("images", ("a.jpg", jpeg_bytes(), "image/jpeg"))],
        data={"focus": "floor"},
    )
    st = _wait(client, res.json()["job_id"])
    assert st["status"] == "failed" and "try again" in st["error"]
    assert client.get(f"{BASE}/{res.json()['report_id']}").json()["materials"] == []


def test_bad_uploads_and_other_users(api):
    client, env = api
    bad = client.post(f"{BASE}", files=[("images", ("a.txt", b"hello", "text/plain"))])
    assert bad.status_code == 400
    many = client.post(
        f"{BASE}", files=[("images", (f"{i}.jpg", jpeg_bytes(), "image/jpeg")) for i in range(5)]
    )
    assert many.status_code == 400
    view = _analyse(client)
    env.user = "user-b"
    assert client.get(f"{BASE}/{view['id']}").status_code == 404
    assert client.post(f"{BASE}/{view['id']}/chat", data={"message": "hi"}).status_code == 404


def test_project_room_at_start(api):
    client, env = api
    env.projects.add("user-a", "p1", "Green Villa", KITCHEN_PLAN)
    env.projects.add("user-b", "p2", "Sea View", KITCHEN_PLAN)
    view = _analyse(client, project_id="p1", room="living", focus="", focus_areas="")
    assert view["project_name"] == "Green Villa"
    assert view["report"]["target"]["label"].startswith("Living, 16 × 14 ft")
    other = _analyse(client, project_id="p2", room="living")
    assert other["project_id"] is None and other["report"]["target"] is None


def test_find_project_scoping():
    src = MemoryProjectSource()
    src.add("u1", "a", "Green Villa")
    src.add("u1", "b", "Green Villa Annexe")
    src.add("u2", "c", "Blue House")
    assert find_project(src, "u1", "green villa").project.id == "a"
    assert find_project(src, "u1", "villa").status == "ambiguous"
    assert find_project(src, "u1", "Blue House").status == "not_found"
    assert find_project(src, "u1", "grean vila").project.id == "a"
    assert find_project(src, "u3", "Green Villa").status == "not_found"


def test_prompt_only_flow(api):
    """Just a photo and a prompt: no focus chips, no space form."""
    client, env = api
    general = _analyse(client, focus_areas="", focus="analyze this interior design")
    assert general["focus"] == "analyze this interior design"
    assert len(general["materials"]) == 3 and general["report"]["lines"] == []
    sized = _analyse(client, focus_areas="", focus="what is on the TV wall? it is 12 x 10 ft")
    assert sized["report"]["target"]["label"] == "TV Wall, 12 × 10 ft"
    assert _line(sized, "veneer")["total_qty"] == 92.4


def test_space_from_prompt():
    from app.modules.ai.material_agent.chat import space_from_text

    assert space_from_text("analyze this interior design") is None
    w = space_from_text("TV wall 12 x 10 ft")
    assert (w.kind, w.length, w.height, w.label) == ("wall", 12, 10, "TV Wall")
    r = space_from_text("my kitchen is 3 x 2.4 m")
    assert (r.kind, r.unit, r.length, r.width, r.label) == ("room", "m", 3, 2.4, "Kitchen")
    h = space_from_text("living room 14 x 12 x 10")
    assert (h.kind, h.height) == ("room", 10)


KITCHEN_PHOTO = __import__(
    "app.modules.ai.material_agent.schemas", fromlist=["ImageAnalysis"]
).ImageAnalysis(
    scene="kitchen",
    materials=[
        {
            "name": "grey quartz countertop",
            "category": "countertop",
            "surface": "countertop",
            "confidence": "medium",
        },
        {
            "name": "grey subway tile backsplash",
            "category": "tile",
            "surface": "backsplash",
            "confidence": "medium",
        },
        {
            "name": "matte white lacquer cabinet doors",
            "category": "cabinet",
            "surface": "cabinet",
            "confidence": "high",
        },
        {
            "name": "grey vitrified floor tile",
            "category": "tile",
            "surface": "floor",
            "confidence": "medium",
        },
        {
            "name": "white emulsion paint",
            "category": "paint",
            "surface": "wall",
            "confidence": "high",
        },
    ],
)
REPLICATE = (
    "I want to replicate the same design that in the image according to my floor plan. "
    "Give me the quantities in what quantities all the materials would be required"
)


def test_replicate_design_with_uploaded_plan(api):
    """The reported case: photo, then 'replicate this design in my floor plan' + plan."""
    client, env = api
    env.vision = FakeVision(KITCHEN_PHOTO)
    view = _analyse(client, focus_areas="", focus="Analyze this interior design")
    r = _chat(client, view["id"], REPLICATE, ("plan.pdf", b"%PDF-1.4 fake", "application/pdf"))
    _wait(client, r["job_id"])
    v = client.get(f"{BASE}/{view['id']}").json()
    last = v["messages"][-1]
    # it never asks "which material?" or "where?": only the platform layout
    assert last["status"] == "needs_input" and "platform layout" in last["text"]
    assert "Which material" not in json.dumps(v["messages"])
    apps = {(ln["material"].split()[1], ln["application"]) for ln in v["report"]["lines"]}
    assert ("vitrified", "Kitchen floor") in apps and ("emulsion", "Kitchen walls") in apps
    done = _chat(client, view["id"], "L-shape")
    assert done["status"] == "ok"
    lines = {ln["application"]: ln for ln in done["session"]["report"]["lines"]}
    assert lines["Kitchen platform (L-shape)"]["total_qty"] == 35.2  # 10 x 8 kitchen
    assert lines["Kitchen backsplash (L-shape)"]["surface_sqft"] == 36.0  # (10 + 8) x 2
    assert lines["Kitchen floor"]["surface_sqft"] == 80.0
    assert env.vision.calls == 1


def test_replicate_without_plan_asks_for_the_plan_once(api):
    client, env = api
    env.vision = FakeVision(KITCHEN_PHOTO)
    view = _analyse(client, focus_areas="", focus="replicate this design in my floor plan")
    assert "Attach your floor plan" in view["messages"][-1]["text"]
    r = _chat(client, view["id"], "give me all the materials quantities")
    assert r["status"] == "needs_input" and "Attach your floor plan" in r["message"]
    assert r["options"] == []


def test_replicate_asks_which_room_when_plan_has_several(api):
    client, env = api
    env.projects.add("user-a", "p1", "Green Villa", KITCHEN_PLAN)
    bedroom_photo = KITCHEN_PHOTO.model_copy(update={"scene": "bedroom"})
    env.vision = FakeVision(bedroom_photo)
    view = _analyse(client, focus_areas="", focus="")
    _chat(client, view["id"], "use project green villa")
    q = _chat(client, view["id"], "same look, all quantities please")
    assert q["status"] == "needs_input" and "All of them" in q["options"] and len(q["options"]) == 3
    both = _chat(client, view["id"], "All of them")
    assert both["status"] == "ok" and "2 rooms" in both["message"]
    rooms = {ln["application"] for ln in both["session"]["report"]["lines"]}
    assert {"Bedroom 1 floor", "Bedroom 2 floor"} <= rooms


def test_explains_how_a_quantity_was_calculated(api):
    client, _ = api
    view = _analyse(client, {"kind": "wall", "length": 12, "height": 10, "label": "TV wall"})
    none_yet = _analyse(client, focus_areas="", focus="analyze this interior design")
    assert (
        "no quantities yet" in _chat(client, none_yet["id"], "how did you calculate it?")["message"]
    )

    r = _chat(client, view["id"], "how did you calculate the veneer quantity?")
    msg = r["message"]
    assert r["status"] == "ok"
    assert "the size you gave" in msg  # where the size came from
    assert "12 × 10 = 120" in msg and "120 × 70% = 84" in msg  # surface, then share
    assert "Wastage 10%" in msg and "92.4" in msg  # wastage and the total
    assert "rounded up" in msg and "estimated from the photo" in msg
    assert "marble" not in msg.lower().split("assumptions panel")[0]  # only the asked line
    why = _chat(client, view["id"], "why 3 sheets?")
    assert "rounded up" in why["message"]
    allq = _chat(client, view["id"], "show me the calculation")
    assert "Fluted walnut veneer panel" in allq["message"] and "Statuario marble" in allq["message"]


class FakeAnswerLLM:
    """Text LLM double: classifies as explain_quantity and phrases an answer."""

    def __init__(self, answer: str) -> None:
        self.answer = answer

    def structured(self, *, system, user, schema, task, images=None):
        from app.modules.ai.material_agent.schemas import ChatIntent, Explanation

        if schema is ChatIntent:
            return ChatIntent(action="explain_quantity", material="veneer")
        assert schema is Explanation and task == "material_answer"
        assert '"why_wastage"' in user and '"steps"' in user  # grounded in the facts
        return Explanation(text=self.answer)


def test_llm_answer_is_used_only_with_real_numbers(api):
    client, env = api
    view = _analyse(client, {"kind": "wall", "length": 12, "height": 10, "label": "TV wall"})
    good = "Wastage of 10% covers cutting and breakage, so 84 sq ft becomes **92.4 sq ft**."
    env_deps = env.deps

    def with_llm(answer):
        def deps():
            d = env_deps()
            d.text_llm = FakeAnswerLLM(answer)
            return d

        return deps

    app.dependency_overrides[get_deps] = with_llm(good)
    assert _chat(client, view["id"], "why so much veneer?")["message"].startswith(good)
    app.dependency_overrides[get_deps] = with_llm("You need 95 sq ft.")  # invented number
    msg = _chat(client, view["id"], "why so much veneer?")["message"]
    assert "95" not in msg and "12 × 10 = 120" in msg


def test_history_lists_opens_and_deletes_analyses(api):
    client, env = api
    first = _analyse(client, {"kind": "wall", "length": 12, "height": 10})
    second = _analyse(client, {"kind": "wall", "length": 14, "height": 10})
    listed = client.get(BASE).json()
    assert [r["id"] for r in listed] == [second["id"], first["id"]]
    assert listed[0]["scene"]
    assert client.get(f"{BASE}/{first['id']}").status_code == 200

    owner = env.user
    env.user = "someone-else"
    assert client.get(BASE).json() == []
    assert client.delete(f"{BASE}/{first['id']}").status_code == 404

    env.user = owner
    assert client.delete(f"{BASE}/{first['id']}").status_code == 204
    assert [r["id"] for r in client.get(BASE).json()] == [second["id"]]
    assert client.get(f"{BASE}/{first['id']}").status_code == 404
