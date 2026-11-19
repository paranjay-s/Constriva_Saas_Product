"""The creator agent: designs a library asset for an area no kit serves (a helipad, a koi pond...).

An agent loop on the Messages API with client-side tools. Each tool call is forwarded to a
Blender session on PlanTo3D (POST /api/creator/...), which runs only a fixed set of operations
in its own folder, with no secrets, a 10-minute limit and a polygon budget. The API key stays
here. When the agent exports, PlanTo3D validates the asset (fits the area, within budget,
preview made) and adds it to the library as unreviewed; builds use it only once it is approved,
or with PLAN3D_USE_UNREVIEWED. Off unless PLAN3D_CREATOR_AGENT is true. Tests use fakes.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("construtiva.plan3d.creator")

PROMPT_FILE = Path(__file__).parent / "prompts" / "creator_v1.md"
STYLE_PY = (
    Path(__file__).resolve().parents[4] / "services" / "planto3d" / "library" / "build" / "style.py"
)
MAX_TURNS = 14
PRICE = {"claude-opus-5-5": (4.0, 20.0)}  # $ per million input / output tokens

_V3 = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}
_MAT = {
    "material": {"type": "string", "description": "a style material name"},
    "color": {"type": "string", "description": "#rrggbb, only when no style material fits"},
    "roughness": {"type": "number"},
    "metallic": {"type": "number"},
}


def _tool(
    name: str, description: str, props: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "input_schema": {"type": "object", "properties": props, "required": required},
    }


TOOLS = [
    _tool(
        "add_box",
        "Add a box from min to max corner (metres).",
        {"name": {"type": "string"}, "min": _V3, "max": _V3, "bevel": {"type": "number"}, **_MAT},
        ["min", "max"],
    ),
    _tool(
        "add_cylinder",
        "Add a cylinder or cone standing on center (its base).",
        {
            "name": {"type": "string"},
            "center": _V3,
            "radius": {"type": "number"},
            "radius_top": {"type": "number"},
            "height": {"type": "number"},
            "segments": {"type": "integer"},
            **_MAT,
        },
        ["center", "radius", "height"],
    ),
    _tool(
        "add_lathe",
        "Add a surface of revolution: profile is [radius, height] pairs, bottom to top.",
        {
            "name": {"type": "string"},
            "center": _V3,
            "profile": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
            "segments": {"type": "integer"},
            **_MAT,
        },
        ["center", "profile"],
    ),
    _tool(
        "add_rod",
        "Add a round bar between two points.",
        {
            "name": {"type": "string"},
            "start": _V3,
            "end": _V3,
            "radius": {"type": "number"},
            **_MAT,
        },
        ["start", "end", "radius"],
    ),
    _tool(
        "set_material",
        "Change an object's material.",
        {"object": {"type": "string"}, **_MAT},
        ["object"],
    ),
    _tool(
        "transform",
        "Move, rotate (degrees) or scale an object.",
        {"object": {"type": "string"}, "location": _V3, "rotation_deg": _V3, "scale": _V3},
        ["object"],
    ),
    _tool("delete", "Delete an object.", {"object": {"type": "string"}}, ["object"]),
    _tool(
        "add_light",
        "Add a small light that belongs to the area (a lantern, an underwater light).",
        {
            "name": {"type": "string"},
            "kind": {"type": "string", "enum": ["POINT", "SPOT", "AREA"]},
            "location": _V3,
            "watts": {"type": "number"},
            "warm": {"type": "boolean"},
        },
        ["location"],
    ),
    _tool("scene", "List the objects with their bounds, and the triangle count.", {}, []),
    _tool(
        "render_preview",
        "Render previews (evening, then day) and see them.",
        {"samples": {"type": "integer"}},
        [],
    ),
    _tool("export", "Export the finished asset (the last step).", {}, []),
]


def style_materials() -> list[str]:
    """the style's material names (style.py RECIPES)"""
    try:
        return re.findall(r'^\s+"(\w+)": lambda', STYLE_PY.read_text("utf-8"), re.M)
    except OSError:
        return []


def system_prompt() -> str:
    mats = style_materials()
    return PROMPT_FILE.read_text("utf-8") + (
        f"\nStyle materials: {', '.join(mats)}\n" if mats else ""
    )


def _client_and_model() -> tuple[Any, str]:
    import anthropic

    from app.modules.parsing.settings import resolve_llm_config

    config = resolve_llm_config()
    if config.provider != "anthropic":
        raise RuntimeError("the creator agent needs the Anthropic provider")
    return anthropic.Anthropic(api_key=config.api_key, max_retries=2, timeout=300), config.model


class CreatorService:
    """the PlanTo3D side of a creator run (synchronous: the run happens in a worker thread)"""

    def __init__(self, base_url: str, timeout_s: float = 660.0) -> None:
        import httpx

        self.http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_s)

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        r = self.http.post(path, json=body)
        r.raise_for_status()
        out: dict[str, Any] = r.json()
        return out

    def creator_start(self, area: str, size_m: list[float]) -> str:
        return str(self._post("/api/creator/start", {"area": area, "size_m": size_m})["session"])

    def creator_op(self, sid: str, op: str, args: dict[str, Any]) -> dict[str, Any]:
        return self._post(f"/api/creator/{sid}/op", {"op": op, "args": args})

    def creator_finish(self, sid: str, meta: dict[str, Any]) -> dict[str, Any]:
        return self._post(f"/api/creator/{sid}/finish", meta)


def run(area: str, name: str, description: str, size_m: list[float]) -> dict[str, Any]:
    """the admin endpoint's entry: off unless PLAN3D_CREATOR_AGENT"""
    from app.modules.plan3d.settings import get_settings

    settings = get_settings()
    if not settings.creator_agent:
        return {"ok": False, "problems": ["the creator agent is off (PLAN3D_CREATOR_AGENT)"]}
    return create(area, name, description, size_m, CreatorService(settings.service_url))


def create(
    area: str,
    name: str,
    description: str,
    size_m: list[float],
    service: Any,
    client: Any = None,
    model: str | None = None,
    max_turns: int = MAX_TURNS,
) -> dict[str, Any]:
    """one asset for one area type -> {"ok", "entry" or "problems", "cost_usd", "turns"}.
    `service` is the PlanTo3D client (creator_start / creator_op / creator_finish); `client` an
    Anthropic client (fakes in tests)."""
    if client is None:
        client, model = _client_and_model()
    model = model or "claude-opus-5-5"
    t0 = time.time()
    sid = service.creator_start(area, size_m)
    w, d, h = size_m
    task = (
        f"Make the area '{name}': {description}\n"
        f"It must fit {w:.2f} m wide (x) by {d:.2f} m deep (y) and at most {h:.2f} m high (z)."
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    tokens_in = tokens_out = turns = 0
    exported = False
    while turns < max_turns:
        turns += 1
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=system_prompt(),
            tools=TOOLS,
            messages=messages,
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        tokens_in += getattr(response.usage, "input_tokens", 0) or 0
        tokens_out += getattr(response.usage, "output_tokens", 0) or 0
        if response.stop_reason == "refusal":
            logger.info("creator for %s: the model declined", area)
            break
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        calls = [b for b in response.content if getattr(b, "type", "") == "tool_use"]
        if response.stop_reason == "end_turn" or not calls:
            break
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for b in calls:
            try:
                out = service.creator_op(sid, b.name, dict(b.input or {}))
            except Exception as e:  # noqa: BLE001 - a failed call is the agent's to handle
                out = {"ok": False, "error": str(e)[:300]}
            png = out.pop("png_b64", None) or []
            content: list[dict[str, Any]] = [{"type": "text", "text": json.dumps(out)[:4000]}]
            for data in [png] if isinstance(png, str) else png:  # evening, then day
                content.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": data},
                    }
                )
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": content,
                    "is_error": not out.get("ok"),
                }
            )
            exported = exported or (b.name == "export" and out.get("ok"))
        messages.append({"role": "user", "content": results})
        if exported:
            break
    pin, pout = PRICE.get(model, (4.0, 20.0))
    cost = round((tokens_in * pin + tokens_out * pout) / 1e6, 4)
    result = service.creator_finish(
        sid, {"prompt": task, "cost_usd": cost, "turns": turns, "model": model}
    )
    result.update(cost_usd=cost, turns=turns, seconds=round(time.time() - t0, 1))
    return result
