"""No money anywhere in the Material Finder, plus the LLM image argument and the store."""

import base64
import json
import re
from pathlib import Path

import httpx
from pydantic import BaseModel

from app.main import app
from app.modules.ai.llm.client import GeminiClient
from app.modules.ai.material_agent import schemas
from app.modules.ai.material_agent.calculator import Applied
from app.modules.ai.material_agent.normalise import normalise
from app.modules.ai.material_agent.schemas import ApplicationRequest, ImageAnalysis, ManualSpace
from app.modules.ai.material_agent.space import manual_target
from app.modules.ai.material_agent.store import Session
from app.modules.ai.material_agent.vision import cache_key
from tests.material_agent.conftest import TV_WALL

AGENT_DIR = Path(__file__).resolve().parents[2] / "app" / "modules" / "ai" / "material_agent"
PROMPT_DIR = Path(__file__).resolve().parents[2] / "app" / "modules" / "ai" / "prompts" / "material"

PROMPT_BANNED = [r"cost", r"price", r"budget", r"₹", r"\brs\.", r"\binr\b", r"\$", r"rate per"]
FIELD_BANNED = ["cost", "price", "rate", "amount_inr", "currency", "budget"]


def test_prompts_never_mention_money():
    files = sorted(PROMPT_DIR.glob("*.md"))
    assert {f.stem for f in files} == {
        "material_vision",
        "material_chat",
        "material_summary",
        "material_answer",
        "material_advice",
    }
    for f in files:
        text = f.read_text(encoding="utf-8").lower()
        for pat in PROMPT_BANNED:
            assert not re.search(pat, text), f"{f.name} contains {pat!r}"


def _field_names(model: type[BaseModel]) -> set[str]:
    names: set[str] = set()
    for name, info in model.model_fields.items():
        names.add(name)
        for arg in getattr(info.annotation, "__args__", ()) or (info.annotation,):
            if isinstance(arg, type) and issubclass(arg, BaseModel):
                names |= _field_names(arg)
    return names


def test_schema_field_names_have_no_money_fields():
    models = [
        v
        for v in vars(schemas).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == schemas.__name__
    ]
    assert len(models) > 15
    names = set().union(*(_field_names(m) for m in models))
    for n in names:
        for bad in FIELD_BANNED:
            assert bad not in n.lower(), f"field {n!r} contains {bad!r}"


def test_api_schema_has_no_money_fields():
    spec = app.openapi()
    paths = {p: v for p, v in spec["paths"].items() if "/material-analysis" in p}
    # Every material-finder path, so a new one is looked at here before it ships.
    # `/{report_id}/image` (the photo of a saved analysis) came with the chat history.
    base = "/api/v1/ai/material-analysis"
    assert set(paths) == {
        base,
        f"{base}/jobs/{{job_id}}",
        f"{base}/jobs/{{job_id}}/events",
        f"{base}/{{report_id}}",
        f"{base}/{{report_id}}/image",
        f"{base}/{{report_id}}/recalculate",
        f"{base}/{{report_id}}/chat",
    }
    assert "/api/v1/ai/analyze-materials" not in spec["paths"]  # the old cost endpoint is gone
    text = json.dumps(paths).lower()
    for bad in ("cost", "price", "budget", "currency", "inr"):
        assert bad not in text


def test_data_files_and_code_have_no_money_words():
    for f in list(AGENT_DIR.rglob("*.json")) + list(AGENT_DIR.rglob("*.py")):
        text = f.read_text(encoding="utf-8").lower()
        if f.name == "chat.py":  # it detects money questions to refuse them
            continue
        for bad in (r"price", r"budget", r"₹", r"inr", r"currency"):
            assert not re.search(bad, text), f"{f.name} contains {bad!r}"


def test_old_cost_module_is_deleted():
    assert not (AGENT_DIR.parent / "material_vision.py").exists()


# ---------------------------------------------------------------- LLM images


def test_llm_client_sends_images_inline_and_text_only_unchanged():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        body = ImageAnalysis(scene="kitchen").model_dump_json()
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": body}]}}]})

    client = GeminiClient(
        model="m", temperature=0, timeout_s=5, api_key="k", transport=httpx.MockTransport(handler)
    )
    out = client.structured(
        system="s", user="u", schema=ImageAnalysis, task="t", images=[(b"abc", "image/jpeg")]
    )
    assert out.scene == "kitchen"
    parts = seen[0]["contents"][0]["parts"]
    assert parts[0]["inline_data"] == {
        "mime_type": "image/jpeg",
        "data": base64.b64encode(b"abc").decode(),
    }
    assert parts[1] == {"text": "u"}
    client.structured(system="s", user="u2", schema=ImageAnalysis, task="t")
    assert seen[1]["contents"][0]["parts"] == [{"text": "u2"}]


def test_vision_cache_key_depends_on_images_focus_and_model():
    k = cache_key(["a", "b"], "TV wall", "m1")
    assert k == cache_key(["b", "a"], " tv wall ", "m1")
    assert k != cache_key(["a", "b"], "ceiling", "m1")
    assert k != cache_key(["a", "b"], "TV wall", "m2")
    assert k != cache_key(["a"], "TV wall", "m1")


def test_session_state_round_trip():
    mats = normalise(TV_WALL.materials)
    target = manual_target(ManualSpace(kind="wall", length=12, height=10))
    s = Session(
        id="s1", owner_id="u1", focus="TV wall", materials=mats, target=target, analysis=TV_WALL
    )
    s.applied.append(
        Applied(
            material_id="m2",
            request=ApplicationRequest(application="platform", layout="l_shape"),
            target=target,
        )
    )
    s.uploaded_plan = {"levels": []}
    s.say("user", "hi")
    state = json.loads(json.dumps(s.state()))
    back = Session.from_state("s1", None, state, s.messages)
    assert back.owner_id == "u1" and back.materials == mats and back.target == target
    assert back.applied[0].request.layout == "l_shape" and back.uploaded_plan == {"levels": []}


def test_fallback_model_gets_its_own_time_limit():
    seen: list[tuple[str, float]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = request.url.path.split("/")[-1].split(":")[0]
        seen.append((model, request.extensions["timeout"]["read"]))
        if model == "slow-main":
            raise httpx.ReadTimeout("slow", request=request)
        body = ImageAnalysis(scene="kitchen").model_dump_json()
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": body}]}}]})

    client = GeminiClient(
        model="slow-main",
        fallback_model="backup",
        temperature=0,
        timeout_s=30,
        fallback_timeout_s=40,
        api_key="k",
        transport=httpx.MockTransport(handler),
    )
    assert (
        client.structured(system="s", user="u", schema=ImageAnalysis, task="t").scene == "kitchen"
    )
    assert seen == [("slow-main", 30), ("backup", 40)]


def test_material_defaults_are_the_fast_model():
    from app.modules.ai.material_agent.settings import MaterialSettings

    s = MaterialSettings(_env_file=None)
    assert s.vision_model == "gemini-3.5-flash-lite" and s.llm_timeout_s <= 30
