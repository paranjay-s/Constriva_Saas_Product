"""Answers questions about the analysis: "how did you calculate this?", "why 10 % wastage?",
"why 3 sheets?", "why do you think it is quartz?", "what did you assume?".

Every answer is built from the same facts the calculator used (QuantityLine breakdowns,
assumptions, sources of sizes and shares, the editable rules). An LLM may phrase the
answer for open "why" questions, but only with those facts, and every number it writes
must appear in them (compose.numbers_ok); otherwise the step-by-step answer below is used.
"""

import json
import logging

from app.modules.ai.llm.client import LLMClient, LLMError
from app.modules.ai.material_agent.compose import numbers_ok
from app.modules.ai.material_agent.data_files import application_rules, rules
from app.modules.ai.material_agent.schemas import (
    Explanation,
    Material,
    Overrides,
    QuantityLine,
    TargetSpace,
)
from app.modules.ai.material_agent.units import fmt
from app.modules.ai.material_agent.vision import prompt

logger = logging.getLogger("construtiva.ai.material.explain")

MAX_LINES = 4


def space_source(t: TargetSpace | None) -> str:
    if t is None:
        return "no size given yet"
    match t.source:
        case "manual":
            return f"{t.label} (the size you gave)"
        case "project":
            return f"{t.label} (from the saved plan of project {t.project_name})"
    return f"{t.label} (from your uploaded floor plan)"


def coverage_source(m: Material | None, line: QuantityLine, overrides: Overrides) -> str:
    pct = fmt(line.coverage_ratio * 100)
    if line.coverage_ratio >= 1:
        return "The material covers the whole surface."
    if m is not None and m.id in overrides.coverage_ratio:
        return f"Share {pct}% of the surface: set by you."
    if m is not None and m.coverage_ratio is not None:
        return f"Share {pct}% of the surface: estimated from the photo ({m.location or m.surface})."
    return (
        f"Share {pct}% of the surface: the photo gave no share, so the surface was split "
        "between the materials on it."
    )


def pick_lines(
    lines: list[QuantityLine], materials: list[Material], material_ids: set[str], words: str
) -> list[QuantityLine]:
    """The lines the question is about: by material, then by place words, else all."""
    chosen = [ln for ln in lines if ln.material_id in material_ids] if material_ids else list(lines)
    low = words.lower()
    by_place = [
        ln for ln in chosen if any(w in low for w in ln.application.lower().split() if len(w) > 3)
    ]
    return (by_place or chosen)[:MAX_LINES]


def step_by_step(
    lines: list[QuantityLine],
    materials: list[Material],
    overrides: Overrides,
) -> str:
    """The calculation of each line, in the order it was done."""
    by_id = {m.id: m for m in materials}
    blocks = []
    for ln in lines:
        m = by_id.get(ln.material_id)
        rows = [f"**{ln.material}, {ln.application}: {fmt(ln.total_qty)} {ln.unit}**"]
        for b in ln.breakdown:
            rows.append(f"- {b.label}: {b.formula} = {fmt(b.value)}")
        rows.append(f"- {coverage_source(m, ln, overrides)}")
        for a in ln.assumptions:
            rows.append(f"- Assumed: {a}")
        blocks.append("\n".join(rows))
    return "\n\n".join(blocks)


def _facts(
    question: str,
    lines: list[QuantityLine],
    materials: list[Material],
    target_note: str,
    overrides: Overrides,
    report_assumptions: list[str],
) -> dict:
    r = rules()
    ar = application_rules()
    by_id = {m.id: m for m in materials}
    return {
        "question": question,
        "space": target_note,
        "lines": [
            {
                "material": ln.material,
                "where": ln.application,
                "total_sq_ft": fmt(ln.total_qty),
                "net_sq_ft": fmt(ln.net_qty),
                "wastage_percent": fmt(ln.wastage_pct),
                "buy": f"{fmt(ln.buy_qty)} {ln.buy_unit}" if ln.buy_qty is not None else None,
                "steps": [f"{b.label}: {b.formula} = {fmt(b.value)}" for b in ln.breakdown],
                "share": coverage_source(by_id.get(ln.material_id), ln, overrides),
                "assumptions": ln.assumptions,
            }
            for ln in lines
        ],
        "materials": [
            {
                "name": m.display_name,
                "surface": m.surface,
                "where_in_photo": m.location,
                "finish": ", ".join(x for x in (m.finish, m.pattern, m.colour, m.size_hint) if x),
                "confidence": m.confidence,
                "recognised_from": m.evidence,
                "could_also_be": m.look_alikes,
            }
            for m in materials
        ],
        "assumptions": report_assumptions,
        "rules": {
            "wastage_percent_by_type": {
                k: v for k, v in r["wastage_pct"].items() if not k.startswith("_")
            },
            "paint": r["paint"],
            "platform_depth_ft": ar["platform_depth_ft"],
            "backsplash_height_ft": ar["backsplash_height_ft"],
            "default_ceiling_height_ft": ar["default_ceiling_height_ft"],
            "why_wastage": "extra for cutting, breakage, pattern matching and offcuts at edges",
            "why_round_up": "sheets, boxes, rolls and litres are bought whole",
            "status": "standard values, to be verified with the architecture firm",
        },
    }


def answer(
    llm: LLMClient | None,
    question: str,
    lines: list[QuantityLine],
    materials: list[Material],
    target: TargetSpace | None,
    overrides: Overrides,
    report_assumptions: list[str],
    fallback: str | None = None,
) -> str:
    if fallback is None:
        fallback = step_by_step(lines, materials, overrides)
        if target is not None:
            fallback = f"Sizes come from {space_source(target)}.\n\n" + fallback
    if llm is None:
        return fallback
    facts = _facts(question, lines, materials, space_source(target), overrides, report_assumptions)
    payload = json.dumps(facts, ensure_ascii=False)
    try:
        out = llm.structured(
            system=prompt("material_answer"),
            user=payload,
            schema=Explanation,
            task="material_answer",
        )
    except LLMError as e:
        logger.info("material answer LLM failed (%s); using the step-by-step answer", e)
        return fallback
    text = out.text.strip()
    if not text or not numbers_ok(text, payload):
        logger.info("material answer used numbers not in the facts; using the step-by-step answer")
        return fallback
    return text


def advise(llm: LLMClient | None, question: str, facts: dict, fallback: str) -> str:
    """Expert advice (alternatives, comparisons, suitability, care...) grounded in the facts."""
    if llm is None:
        return fallback
    payload = json.dumps({"question": question, "facts": facts}, ensure_ascii=False)
    try:
        out = llm.structured(
            system=prompt("material_advice"),
            user=payload,
            schema=Explanation,
            task="material_advice",
        )
    except LLMError as e:
        logger.info("material advice LLM failed (%s); using the catalog answer", e)
        return fallback
    text = out.text.strip()
    if not text or not numbers_ok(text, payload):
        logger.info("material advice had numbers not in the facts; using the catalog answer")
        return fallback
    return bullets_on_lines(text)


def bullets_on_lines(text: str) -> str:
    """'Yes. - point one. - point two' -> one bullet per line (models sometimes inline them)."""
    if "\n" in text or " - " not in text:
        return text
    head, *points = text.split(" - ")
    return head.strip() + "\n" + "\n".join(f"- {p.strip()}" for p in points if p.strip())
