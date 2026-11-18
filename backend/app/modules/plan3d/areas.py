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

PROMPT_VERSION = "areas-1"
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
                    "spec": {
                        "type": "object",
                        "description": (
                            "only for 'new': {type, name, description, surface, "
                            "edge (none|kerb|low_wall|fence|railing), "
                            "height {mode flat|raised|recessed, value_m}, walkable, "
                            "markings [{kind line|circle|arc|text, from, to, centre, radius, "
                            "start_deg, end_deg, width_m, at, text (A-Z 0-9), size_m}], "
                            "objects [{part, at, rot}]}"
                        ),
                    },
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
