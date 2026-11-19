"""The AI gap-filler: one call per plan fills in what the readers missed, from the drawing.

Input: the page image, the reader's plan (rooms with ids, labels, types and boxes in the image's
pixels) and what is missing or doubtful. Output (a fixed schema): room names and types, a
numbered legend, missing walls and openings, a scale. Names, types and legends are applied
(source "ai" with the model's confidence). A wall is added only where the drawing supports it
(PlanTo3D POST /support: fills or pen strokes on both faces); otherwise it is a suggestion on
the review page, never a wall in the build. Openings and scale are suggestions. Off unless
PLAN3D_AI_GAPFILL is true; cached by prompt version, plan and image; if the call fails the plan
goes on without it. Tests use fakes: no live model.
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("construtiva.plan3d.gapfill")

PROMPT_FILE = Path(__file__).parent / "prompts" / "gapfill_v1.md"
PROMPT_VERSION = PROMPT_FILE.stem
CACHE = Path(__file__).resolve().parents[3] / ".tmp" / "gapfill_cache"
PX_PER_PT = 100 / 72  # PlanTo3D renders page images at 100 dpi
SUPPORTED = 0.6  # share of a proposed wall the drawing must back
CONFIDENT = 0.6
MOST = 40

_PT = {"type": "array", "items": {"type": "number"}, "description": "[x, y] image pixels"}
_ITEM = {"reason": {"type": "string"}, "confidence": {"type": "number"}}
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rooms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "floor": {"type": "integer"},
                    "room_id": {"type": "integer"},
                    "label": {"type": "string"},
                    "type": {"type": "string"},
                    **_ITEM,
                },
                "required": ["floor", "room_id", "label", "type", "confidence"],
            },
        },
        "legend": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"number": {"type": "string"}, "name": {"type": "string"}},
                "required": ["number", "name"],
            },
        },
        "walls": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"floor": {"type": "integer"}, "from": _PT, "to": _PT, **_ITEM},
                "required": ["floor", "from", "to", "confidence"],
            },
        },
        "openings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "floor": {"type": "integer"},
                    "kind": {"type": "string", "enum": ["door", "window"]},
                    "at": _PT,
                    "width_px": {"type": "number"},
                    **_ITEM,
                },
                "required": ["floor", "kind", "at", "confidence"],
            },
        },
        "scale": {"type": "object", "properties": {"feet_per_100px": {"type": "number"}, **_ITEM}},
    },
    "required": ["rooms", "legend", "walls", "openings"],
}


# ------------------------------------------------ plan feet <-> image pixels (per storey)
def _frame(plan: dict[str, Any], f: dict[str, Any]) -> tuple[float, float, float] | None:
    s = plan.get("scale_pt_per_ft")
    o = f.get("origin_pt")
    if not s or not o:
        return (
            None  # a plan made without a drawing frame (AI read, traced): no geometry from the AI
        )
    return float(o[0]), float(o[1]), float(s)


def to_px(fr: tuple[float, float, float], x: float, y: float) -> tuple[float, float]:
    X0, Y1, s = fr
    return (X0 + x * s) * PX_PER_PT, (Y1 - y * s) * PX_PER_PT


def to_ft(fr: tuple[float, float, float], px: float, py: float) -> tuple[float, float]:
    X0, Y1, s = fr
    return (px / PX_PER_PT - X0) / s, (Y1 - py / PX_PER_PT) / s


def request_text(plan: dict[str, Any], types: list[str]) -> str:
    """what the model is told about the reading"""
    lines = [f"Room types: {', '.join(types)}"]
    for k, f in enumerate(plan.get("floors", [])):
        fr = _frame(plan, f)
        lines.append(f"Storey {k} ({f.get('name') or ''}):")
        for i, r in enumerate(f.get("rooms", [])):
            q = (r.get("rects") or [[0, 0, 0, 0]])[0]
            if fr:
                (ax, ay), (bx, by) = to_px(fr, q[0], q[3]), to_px(fr, q[1], q[2])
                box = f"box px [{ax:.0f}, {ay:.0f}, {bx:.0f}, {by:.0f}]"
            else:
                box = "box unknown"
            lines.append(
                f"  room {i}: label {r.get('label') or '(none)'!r}, type {r.get('type')}, {box}"
            )
    issues = [
        c.get("message")
        for c in plan.get("checks") or []
        if c.get("severity") in ("critical", "warning")
    ]
    lines.append("Missing or doubtful:")
    lines += [f"- {m}" for m in issues[:30]] or ["- (nothing flagged)"]
    return "\n".join(lines)


def ask(
    plan: dict[str, Any], page_png: bytes, types: list[str], client: Any = None
) -> dict[str, Any]:
    """the model's answer, validated loosely (apply() checks every field), cached"""
    text = request_text(plan, types)
    system = PROMPT_FILE.read_text("utf-8")
    key = hashlib.sha256(
        f"{PROMPT_VERSION}\n{text}".encode() + hashlib.sha256(page_png).digest()
    ).hexdigest()
    path = CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text("utf-8"))
    from app.modules.ai.llm.json_client import LLMImage

    if client is None:
        from app.modules.parsing.llm_parser import build_client

        client = build_client()
    reply = client.generate_json(
        system_prompt=system, images=[LLMImage(page_png)], text=text, json_schema=SCHEMA
    )
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reply), "utf-8")
    return reply if isinstance(reply, dict) else {}


def _num(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


def _pt(v: Any) -> bool:
    return isinstance(v, list) and len(v) == 2 and all(_num(c) for c in v)


async def apply(
    plan: dict[str, Any],
    reply: dict[str, Any],
    types: list[str],
    service: Any,
    job_id: str,
    classify: Any = None,
) -> dict[str, int]:
    """put the answer into the plan: names and types, legend names, supported walls; the rest
    as suggestions"""
    floors = plan.get("floors", [])
    done = dict(rooms=0, legend=0, walls=0, suggestions=0)
    suggestions: list[dict[str, Any]] = []

    def unsure(r: dict[str, Any]) -> bool:
        lab = (r.get("label") or "").strip()
        return (
            not lab
            or bool(re.fullmatch(r"[\d\s.,]+", lab))
            or r.get("type") in ("multipurpose", "room", None)
        )

    for it in (reply.get("rooms") or [])[:MOST]:
        k, i = it.get("floor"), it.get("room_id")
        if not (isinstance(k, int) and 0 <= k < len(floors) and isinstance(i, int)):
            continue
        rooms = floors[k].get("rooms", [])
        if (
            not (0 <= i < len(rooms))
            or not _num(it.get("confidence"))
            or it["confidence"] < CONFIDENT
        ):
            continue
        r = rooms[i]
        if not unsure(r) or it.get("type") not in types or not str(it.get("label") or "").strip():
            continue
        r["label"], r["type"] = str(it["label"]).strip()[:80], it["type"]
        r["src"], r["confidence"] = "ai", round(float(it["confidence"]), 2)
        done["rooms"] += 1
    # a numbered legend: rooms labelled with a number take the legend's name (and its type)
    legend = {
        str(e.get("number")).strip(): str(e.get("name")).strip()[:80]
        for e in (reply.get("legend") or [])[:200]
        if isinstance(e, dict)
        and str(e.get("number") or "").strip()
        and str(e.get("name") or "").strip()
    }
    if legend:
        for f in floors:
            for r in f.get("rooms", []):
                m = re.match(r"^\s*(\d+)\b", r.get("label") or "")
                if m and m.group(1) in legend and unsure(r):
                    name = legend[m.group(1)]
                    typ = classify(name) if classify else None
                    r["label"] = name
                    if typ in types:
                        r["type"] = typ
                    r["src"] = "ai"
                    done["legend"] += 1
    # walls: added only where the drawing backs them
    by_floor: dict[int, list[tuple[dict[str, Any], list[float]]]] = {}
    for it in (reply.get("walls") or [])[:MOST]:
        k = it.get("floor")
        if not (
            isinstance(k, int)
            and 0 <= k < len(floors)
            and _pt(it.get("from"))
            and _pt(it.get("to"))
        ):
            continue
        fr = _frame(plan, floors[k])
        if not fr:
            suggestions.append(
                dict(
                    floor=k,
                    kind="ai_suggestion",
                    severity="warning",
                    item=["plan", 0],
                    message=f"AI: a wall may be missing ({it.get('reason') or 'no reason given'})",
                )
            )
            continue
        (ax, ay), (bx, by) = to_ft(fr, *it["from"]), to_ft(fr, *it["to"])
        by_floor.setdefault(k, []).append(
            (it, [round(ax, 3), round(ay, 3), round(bx, 3), round(by, 3)])
        )
    thick = (plan.get("wall_pt") or 4.0) / (plan.get("scale_pt_per_ft") or 1.0)
    for k, items in by_floor.items():
        try:
            cover = await service.support(job_id, k, [seg for _, seg in items])
        except Exception as e:  # noqa: BLE001 - no support check: everything stays a suggestion
            logger.info("support check failed for %s: %s", job_id, type(e).__name__)
            cover = [0.0] * len(items)
        for (it, (ax, ay, bx, by)), c in zip(items, cover, strict=False):
            if c >= SUPPORTED and _num(it.get("confidence")) and it["confidence"] >= CONFIDENT:
                h = thick / 2
                if abs(bx - ax) >= abs(by - ay):
                    y = (ay + by) / 2
                    box = [min(ax, bx), max(ax, bx), y - h, y + h, 0]
                else:
                    x = (ax + bx) / 2
                    box = [x - h, x + h, min(ay, by), max(ay, by), 0]
                floors[k]["walls"].append([round(v, 3) for v in box[:4]] + [0])
                floors[k].setdefault("ai_walls", []).append(
                    dict(rect=box[:4], reason=it.get("reason"), support=c)
                )
                done["walls"] += 1
            else:
                suggestions.append(
                    dict(
                        floor=k,
                        kind="ai_suggestion",
                        severity="warning",
                        item=["plan", 0],
                        at=[round((ax + bx) / 2, 2), round((ay + by) / 2, 2)],
                        message=f"AI suggests a wall the drawing does not clearly show "
                        f"({it.get('reason') or 'no reason given'}): add it if it is there",
                    )
                )
    for it in (reply.get("openings") or [])[:MOST]:
        k = it.get("floor")
        if (
            isinstance(k, int)
            and 0 <= k < len(floors)
            and it.get("kind") in ("door", "window")
            and _pt(it.get("at"))
        ):
            fr = _frame(plan, floors[k])
            at = [round(v, 2) for v in to_ft(fr, *it["at"])] if fr else [0, 0]
            suggestions.append(
                dict(
                    floor=k,
                    kind="ai_suggestion",
                    severity="warning",
                    item=["plan", 0],
                    at=at,
                    message=f"AI: a {it['kind']} may be missing here "
                    f"({it.get('reason') or 'no reason given'})",
                )
            )
    sc = reply.get("scale") or {}
    if (
        plan.get("scale_source") == "assumed"
        and _num(sc.get("feet_per_100px"))
        and sc["feet_per_100px"] > 0
    ):
        suggestions.append(
            dict(
                floor=0,
                kind="ai_suggestion",
                severity="warning",
                item=["plan", 0],
                message=f"AI estimates the scale at {sc['feet_per_100px']:.1f} ft per 100 px "
                "of the page "
                "image: confirm one known length with the Scale tool",
            )
        )
    plan["checks"] = [
        c for c in plan.get("checks") or [] if c.get("kind") != "ai_suggestion"
    ] + suggestions[:MOST]
    done["suggestions"] = len(suggestions[:MOST])
    return done


_done: set[str] = set()
_tasks: set = set()


async def run(
    job_id: str, service: Any, ask_fn: Any = None, classify: Any = None
) -> dict[str, int]:
    """the gap-filler for one job, once per process"""
    from fastapi.concurrency import run_in_threadpool

    if job_id in _done:
        return {}
    _done.add(job_id)
    plan = await service.plan(job_id)
    types = await service.room_types()
    page = await service.page_png(job_id)
    reply = await run_in_threadpool(ask_fn or ask, plan, page, types)
    if classify is None:
        from app.modules.plan3d.convert import ROOMS

        classify = lambda name: (ROOMS.classify(name) or (None,))[0]  # noqa: E731
    done = await apply(plan, reply or {}, types, service, job_id, classify)
    await service.save_plan(job_id, plan)
    return done


def start(job_id: str, service: Any) -> None:
    import asyncio

    from app.modules.plan3d.settings import get_settings

    if not get_settings().ai_gapfill or job_id in _done:
        return

    async def go() -> None:
        try:
            done = await run(job_id, service)
            logger.info("gap-filler for %s: %s", job_id, done)
        except Exception as e:  # noqa: BLE001 - the plan goes on without it
            logger.warning("gap-filler for %s failed: %s", job_id, type(e).__name__)

    task = asyncio.get_running_loop().create_task(go())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
