"""Step F: the explanation under the report.

The LLM may phrase it, but every number in its text must already be in the report
(numbers_ok). If not, or without an LLM, a fixed template is used instead. Either way the
quantities shown in the table come from calculator.py, never from this text.
"""

import json
import logging
import re

from app.modules.ai.llm.client import LLMClient, LLMError
from app.modules.ai.material_agent.schemas import Explanation, Material, MaterialReport
from app.modules.ai.material_agent.units import fmt
from app.modules.ai.material_agent.vision import prompt

logger = logging.getLogger("construtiva.ai.material.compose")

_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers(text: str) -> set[float]:
    out = set()
    for n in _NUM.findall(text):
        try:
            out.add(round(float(n.replace(",", "")), 3))
        except ValueError:
            pass
    return out


def numbers_ok(text: str, allowed_source: str) -> bool:
    """True if every number in `text` also appears in `allowed_source`."""
    allowed = _numbers(allowed_source)
    allowed |= {round(v * 100, 3) for v in allowed if v <= 1}  # 0.7 may be written 70 %
    return _numbers(text) <= allowed


def _report_payload(report: MaterialReport, materials: list[Material]) -> dict:
    return {
        "space": report.target.label if report.target else None,
        "materials": [
            {"id": m.id, "name": m.display_name, "surface": m.surface, "confidence": m.confidence}
            for m in materials
        ],
        "quantities": [
            {
                "material": ln.material,
                "where": ln.application,
                "total_sq_ft": fmt(ln.total_qty),
                "wastage_percent": fmt(ln.wastage_pct),
                "buy": f"{fmt(ln.buy_qty)} {ln.buy_unit}" if ln.buy_qty is not None else None,
            }
            for ln in report.lines
        ],
        "assumptions": report.assumptions[:4],
    }


def template_explanation(report: MaterialReport, materials: list[Material]) -> str:
    if not materials:
        return "No finish materials could be identified in this photo."
    names = ", ".join(f"{m.display_name} ({m.surface})" for m in materials[:6])
    more = f" and {len(materials) - 6} more" if len(materials) > 6 else ""
    parts = [f"Found {names}{more}."]
    if report.lines:
        qty = []
        for ln in report.lines[:4]:
            buy = f", about {fmt(ln.buy_qty)} {ln.buy_unit}" if ln.buy_qty is not None else ""
            qty.append(
                f"{ln.material} for {ln.application}: {fmt(ln.total_qty)} sq ft including "
                f"{fmt(ln.wastage_pct)}% wastage{buy}"
            )
        parts.append("; ".join(qty) + ".")
    elif report.target is None:
        parts.append("Add the room or wall size to get quantities.")
    notes = [a for a in report.assumptions if a not in " ".join(parts)]
    if notes:
        parts.append(f"Assumed: {notes[0]}")
    return " ".join(parts)


def explain(llm: LLMClient | None, report: MaterialReport, materials: list[Material]) -> str:
    fallback = template_explanation(report, materials)
    if llm is None or not report.lines:
        return fallback
    payload = json.dumps(_report_payload(report, materials), ensure_ascii=False)
    try:
        out = llm.structured(
            system=prompt("material_summary"),
            user=payload,
            schema=Explanation,
            task="material_summary",
        )
    except LLMError as e:
        logger.info("material summary LLM failed (%s); using the template", e)
        return fallback
    text = out.text.strip()
    if not text or not numbers_ok(text, payload):
        logger.info("material summary had numbers not in the report; using the template")
        return fallback
    return text
