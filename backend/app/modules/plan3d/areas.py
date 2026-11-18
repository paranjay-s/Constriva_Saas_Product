"""Room labels no rule knows: one AI call per plan classifies them all.

For each label the model either picks one of PlanTo3D's room types (with a confidence) or
answers "new" with an area spec in PlanTo3D's fixed schema (services/planto3d/areaspec.py:
surface, edge, height, walkable, markings, objects). Specs are data; PlanTo3D validates them
and builds them with its own tested code. Answers are cached by the set of labels and the
prompt version (backend/.tmp/area_cache), so a plan, or another plan with the same labels,
costs no second call. Tests replace the client: no live model in tests.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("construtiva.plan3d.areas")

PROMPT_VERSION = "areas-2"
CACHE = Path(__file__).resolve().parents[3] / ".tmp" / "area_cache"
SURFACES = ["concrete", "asphalt", "grass", "turf", "sand", "gravel", "wood_deck", "stone", "tile",
            "rubber",
            "water", "clay", "pavers"]  # fmt: skip
PARTS = ["plant", "outdoor_set", "car", "bench", "lamp", "post", "flag"]

SYSTEM = """You classify room and area labels from architectural floor plans for a 3D builder. For
each label, either choose the best matching type from the given list, or, when the label
names an area that none of those types can represent (for example a helipad, an archery
range or a koi pond), answer "new" and describe how to build it with the given schema.
Coordinates u, v are fractions 0-1 of the area's bounding box; sizes are metres. Use
only the listed surfaces and parts. Keep markings to what a person would see painted on
the ground (at most 40). Answer with JSON only."""

_UV = {"type": "array", "items": {"type": "number"}, "description": "[u, v], each 0-1"}
SPEC: dict[str, Any] = {
    "type": "object",
    "description": "only when type is 'new': how to build the area (services/planto3d/areaspec.py)",
    "properties": {
        "type": {"type": "string", "description": "short snake_case name, e.g. helipad"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "surface": {"type": "string", "enum": SURFACES},
        "edge": {"type": "string", "enum": ["none", "kerb", "low_wall", "fence", "railing"]},
        "height": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["flat", "raised", "recessed"]},
                "value_m": {"type": "number", "description": "0-3"},
            },
            "required": ["mode", "value_m"],
        },
        "walkable": {"type": "boolean"},
        "markings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["line", "circle", "arc", "text"]},
                    "from": _UV,
                    "to": _UV,
                    "centre": _UV,
                    "radius": {"type": "number", "description": "fraction of the shorter side"},
                    "start_deg": {"type": "number"},
                    "end_deg": {"type": "number"},
                    "width_m": {"type": "number"},
                    "at": _UV,
                    "text": {"type": "string", "description": "A-Z and 0-9 only"},
                    "size_m": {"type": "number"},
                },
                "required": ["kind"],
            },
        },
        "objects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "part": {"type": "string", "enum": PARTS},
                    "at": _UV,
                    "rot": {"type": "number", "description": "degrees"},
                },
                "required": ["part", "at"],
            },
        },
    },
    "required": ["type", "name", "surface", "edge", "height", "walkable", "markings", "objects"],
}

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "type": {"type": "string", "description": "one of the given types, or 'new'"},
                    "confidence": {"type": "number"},
                    "spec": SPEC,
                },
                "required": ["label", "type", "confidence"],
            },
        }
    },
    "required": ["labels"],
}


def _key(labels: list[str]) -> str:
    joined = "\n".join(sorted({label.strip().upper() for label in labels}))
    return hashlib.sha256(f"{PROMPT_VERSION}\n{joined}".encode()).hexdigest()


def classify_labels(
    labels: list[str], types: list[str], client: Any = None
) -> dict[str, dict[str, Any]]:
    """{label: {"type", "confidence", "spec"?}} for every label; {} when nothing could be asked.
    One call for all the labels (cached)."""
    labels = [label for label in dict.fromkeys(label.strip() for label in labels) if label]
    if not labels:
        return {}
    path = CACHE / f"{_key(labels)}.json"
    if path.exists():
        reply = json.loads(path.read_text("utf-8"))
    else:
        if client is None:
            from app.modules.parsing.llm_parser import build_client

            client = build_client()
        text = (
            f"Types: {', '.join(types)}\nSurfaces: {', '.join(SURFACES)}\n"
            f"Parts: {', '.join(PARTS)}\nLabels:\n" + "\n".join(f"- {label}" for label in labels)
        )
        reply = client.generate_json(system_prompt=SYSTEM, images=[], text=text, json_schema=SCHEMA)
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(reply), "utf-8")
    out: dict[str, dict[str, Any]] = {}
    wanted = {label.upper(): label for label in labels}
    for item in reply.get("labels", []) if isinstance(reply, dict) else []:
        if not isinstance(item, dict):
            continue
        label = wanted.get(str(item.get("label", "")).strip().upper())
        typ = item.get("type")
        conf = item.get("confidence")
        if label is None or not isinstance(typ, str) or not isinstance(conf, int | float):
            continue
        if typ == "new" and isinstance(item.get("spec"), dict):
            out[label] = {"type": "new", "confidence": float(conf), "spec": item["spec"]}
        elif typ in types:
            out[label] = {"type": typ, "confidence": float(conf)}
    return out


CONFIDENT = 0.6
_typed: set[str] = set()
_tasks: set = set()


async def type_unknown_rooms(job_id: str, client: Any, classify: Any = None) -> int:
    """Rooms of a plan whose label no rule knows: one classification for all of them. A known type
    the model is sure of (>= 0.6) is applied; a new area type is added to PlanTo3D's library and
    the room is built from it (type "custom"); the rest stay "multipurpose" (Needs checking).
    -> number of rooms changed. Runs once per job in this process."""
    from fastapi.concurrency import run_in_threadpool

    if job_id in _typed:
        return 0
    _typed.add(job_id)
    plan = await client.plan(job_id)
    rooms = [r for f in plan.get("floors", []) for r in f.get("rooms", [])]
    unknown = [
        r for r in rooms if r.get("type") == "multipurpose" and (r.get("label") or "").strip()
    ]
    if not unknown:
        return 0
    types = await client.room_types() if hasattr(client, "room_types") else []
    answers = await run_in_threadpool(
        classify or classify_labels, [r["label"] for r in unknown], types
    )
    changed = 0
    for r in unknown:
        a = answers.get(r["label"].strip())
        if not a or a["confidence"] < CONFIDENT:
            continue
        if a["type"] == "new":
            try:
                r["area_type"] = await client.save_area(a["spec"])
            except Exception as e:  # noqa: BLE001 - a refused spec leaves the room flagged
                logger.info("area spec for %r refused: %s", r["label"], e)
                continue
            r["type"] = "custom"
        else:
            r["type"] = a["type"]
        r["src"], r["confidence"] = "ai", round(a["confidence"], 2)
        changed += 1
    if changed:
        await client.save_plan(job_id, plan)
    return changed


def start(job_id: str, client: Any) -> None:
    """type the job's unknown rooms in the background (once)"""
    import asyncio

    if job_id in _typed:
        return

    async def run() -> None:
        try:
            await type_unknown_rooms(job_id, client)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "could not classify the unknown rooms of %s: %s", job_id, type(e).__name__
            )

    task = asyncio.get_running_loop().create_task(run())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
