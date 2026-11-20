"""PLAN3D_AI_POLISH (off by default): an AI look at a finished set of High stills, as a photo
editor would.

One AI call per set (cached by the pictures): the model sees every still with its name and may
ask, per still, for an exposure change (EV, within MAX_EV) and a white balance (kelvin, KELVIN).
The answer is data that is validated here; the stills it names are rendered again by PlanTo3D
with those settings (POST /stills with `redo`). The AI never edits a picture or writes code.
Tests use a fake client: no live model in tests.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("construtiva.plan3d.polish")

PROMPT_VERSION = "polish-1"
CACHE = Path(__file__).resolve().parents[3] / ".tmp" / "polish_cache"
MAX_EV = 1.5
KELVIN = (3500, 6500)
MOST = 12

SYSTEM = (
    "You are a photo editor for architectural renders of a villa. You get finished renders, each "
    "named. For a render that is clearly too dark, too bright or has a wrong colour cast, give an "
    "exposure change in EV and, if needed, a white balance in kelvin. Leave good renders out. Do "
    "not comment on design. Answer with JSON only."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "fixes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "ev": {"type": "number"},
                    "kelvin": {"type": "number"},
                    "why": {"type": "string"},
                },
                "required": ["name", "ev"],
            },
        }
    },
    "required": ["fixes"],
}


def fixes(stills: list[tuple[str, bytes]], client: Any = None) -> dict[str, dict[str, Any]]:
    """name -> {"ev", "kelvin" (or None), "why"} for the stills the model would change"""
    if not stills:
        return {}
    h = hashlib.sha256(PROMPT_VERSION.encode())
    for name, data in stills:
        h.update(name.encode() + hashlib.sha256(data).digest())
    path = CACHE / f"{h.hexdigest()}.json"
    if path.exists():
        reply = json.loads(path.read_text("utf-8"))
    else:
        from app.modules.ai.llm.json_client import LLMImage

        if client is None:
            from app.modules.parsing.llm_parser import build_client

            client = build_client()
        reply = client.generate_json(
            system_prompt=SYSTEM,
            images=[LLMImage(data) for _, data in stills],
            text="The renders, in order: " + ", ".join(name for name, _ in stills),
            json_schema=SCHEMA,
        )
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(reply), "utf-8")
    names = {n for n, _ in stills}
    out: dict[str, dict[str, Any]] = {}
    for f in (reply or {}).get("fixes", []) if isinstance(reply, dict) else []:
        if not isinstance(f, dict) or f.get("name") not in names:
            continue
        ev, k = f.get("ev"), f.get("kelvin")
        if not isinstance(ev, int | float) or isinstance(ev, bool):
            continue
        ev = round(max(-MAX_EV, min(MAX_EV, float(ev))), 2)
        kelvin = (
            int(max(KELVIN[0], min(KELVIN[1], float(k))))
            if isinstance(k, int | float) and not isinstance(k, bool)
            else None
        )
        if abs(ev) < 0.1 and kelvin is None:
            continue
        out[f["name"]] = {"ev": ev, "kelvin": kelvin, "why": str(f.get("why") or "")[:200]}
        if len(out) >= MOST:
            break
    return out
