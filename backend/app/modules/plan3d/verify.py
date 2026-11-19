"""A second look at a read plan: one AI call compares the drawing with what was read (rooms, their
labels and sizes, door and window counts) and lists what differs. The differences join the plan's
"Needs checking" list as `ai_review` items; nothing in the plan is changed. Off unless
PLAN3D_AI_VERIFY is true (each plan costs one call). Cached by the plan's summary and the page
image, so a plan is never asked about twice. Tests use a fake client: no live model in tests.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("construtiva.plan3d.verify")

PROMPT_VERSION = "verify-1"
CACHE = Path(__file__).resolve().parents[3] / ".tmp" / "verify_cache"
KINDS = (
    "missing_room",
    "extra_room",
    "wrong_label",
    "wrong_size",
    "missing_door",
    "missing_window",
    "other",
)
MOST = 25

SYSTEM = (
    "You check an automatic reading of an architectural floor plan against the drawing. You get "
    "the drawing and a list of what was read: each storey's rooms with their labels and sizes, and "
    "how many doors and windows each room has. List only real differences a person should check: "
    "a room in the drawing that was not read, a room that was read but is not in the drawing, a "
    "label read wrongly, a size far from the one written in the drawing, a door or window that "
    "was missed. Say where (storey and room). Do not comment on style. Answer with JSON only."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "differences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "storey": {"type": "string"},
                    "room": {"type": "string"},
                    "message": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["kind", "message", "confidence"],
            },
        }
    },
    "required": ["differences"],
}


def summary(plan: dict[str, Any]) -> str:
    """what was read, as the model is shown it"""
    lines = []
    for k, f in enumerate(plan.get("floors", [])):
        lines.append(f"Storey {f.get('name') or k}:")
        ops = f.get("openings", [])
        for r in f.get("rooms", []):
            rects = r.get("rects") or []
            area = sum((q[1] - q[0]) * (q[3] - q[2]) for q in rects)

            def near(o: dict[str, Any], rects: list = rects) -> bool:
                x0, x1, y0, y1 = o["rect"]
                return any(
                    q[0] - 1 <= x1 and x0 <= q[1] + 1 and q[2] - 1 <= y1 and y0 <= q[3] + 1
                    for q in rects
                )

            doors = sum(1 for o in ops if o.get("type") == "door" and near(o))
            wins = sum(1 for o in ops if o.get("type") == "window" and near(o))
            lines.append(
                f"- {r.get('label') or '(no label)'} [{r.get('type')}], {area:.0f} sq ft, "
                f"{doors} doors, {wins} windows"
            )
    return "\n".join(lines)


def differences(plan: dict[str, Any], page_png: bytes, client: Any = None) -> list[dict[str, Any]]:
    """the model's list of differences (validated, at most MOST), cached"""
    text = summary(plan)
    key = hashlib.sha256(
        PROMPT_VERSION.encode() + text.encode() + hashlib.sha256(page_png).digest()
    ).hexdigest()
    path = CACHE / f"{key}.json"
    if path.exists():
        reply = json.loads(path.read_text("utf-8"))
    else:
        from app.modules.ai.llm.json_client import LLMImage

        if client is None:
            from app.modules.parsing.llm_parser import build_client

            client = build_client()
        reply = client.generate_json(
            system_prompt=SYSTEM,
            images=[LLMImage(page_png)],
            text="What was read:\n" + text,
            json_schema=SCHEMA,
        )
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(reply), "utf-8")
    out = []
    for d in (reply or {}).get("differences", []) if isinstance(reply, dict) else []:
        if not isinstance(d, dict) or d.get("kind") not in KINDS:
            continue
        msg, conf = d.get("message"), d.get("confidence")
        if not isinstance(msg, str) or not msg.strip() or not isinstance(conf, int | float):
            continue
        out.append(
            {
                "kind": d["kind"],
                "storey": str(d.get("storey") or "")[:60],
                "room": str(d.get("room") or "")[:80],
                "message": msg.strip()[:300],
                "confidence": round(max(0.0, min(1.0, float(conf))), 2),
            }
        )
    return out[:MOST]


def as_checks(plan: dict[str, Any], found: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Needs-checking items (checks.py's shape) for the differences, on the storey they name"""
    names = [str(f.get("name") or "") for f in plan.get("floors", [])]
    out = []
    for d in found:
        floor = next((k for k, n in enumerate(names) if n and n.lower() == d["storey"].lower()), 0)
        where = f"{names[floor] or 'Plan'}: " if names else ""
        room = f'"{d["room"]}": ' if d["room"] else ""
        out.append(
            {
                "floor": floor,
                "kind": "ai_review",
                "item": ["plan", 0],
                "message": f"{where}{room}{d['message']} (AI second look)",
                "confidence": d["confidence"],
            }
        )
    return out


_done: set[str] = set()
_tasks: set = set()


async def review(job_id: str, client: Any, ask: Any = None) -> int:
    """add the AI's differences to the job's Needs-checking list, once per job in this process"""
    from fastapi.concurrency import run_in_threadpool

    if job_id in _done:
        return 0
    _done.add(job_id)
    plan = await client.plan(job_id)
    page = await client.page_png(job_id)
    found = await run_in_threadpool(ask or differences, plan, page)
    if not found:
        return 0
    plan["checks"] = [c for c in plan.get("checks") or [] if c.get("kind") != "ai_review"]
    plan["checks"] += as_checks(plan, found)
    await client.save_plan(job_id, plan)
    return len(found)


def start(job_id: str, client: Any) -> None:
    """the second look in the background (when PLAN3D_AI_VERIFY is on)"""
    import asyncio

    from app.modules.plan3d.settings import get_settings

    if not get_settings().ai_verify or job_id in _done:
        return

    async def run() -> None:
        try:
            await review(job_id, client)
        except Exception as e:  # noqa: BLE001 - the review page works without the second look
            logger.warning("AI second look at %s failed: %s", job_id, type(e).__name__)

    task = asyncio.get_running_loop().create_task(run())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
