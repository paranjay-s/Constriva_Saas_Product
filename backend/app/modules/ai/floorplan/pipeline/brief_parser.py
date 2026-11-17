"""Brief parser: form + free text (typed or spoken) -> one validated Brief.

The LLM only reads the free text into a `TextBrief` (no coordinates, unstated fields
stay null). Code merges it with the form:
  - the description (prompt) wins over the form; every disagreement is recorded in
    `brief.conflicts` so the confirmation card shows it
  - unknown fields stay empty and are listed in `brief.unknowns`
  - any default used so generation can proceed is listed in `brief.assumptions`
If the LLM is unavailable the form alone is used and a warning says so.
"""

import json
import logging
import math
from dataclasses import dataclass, field

from app.modules.ai.floorplan.prompts import load_prompt
from app.modules.ai.floorplan.rules import DEFAULT_PLOT_RATIO
from app.modules.ai.floorplan.schemas.brief import (
    Brief,
    BriefForm,
    Conflict,
    PlotSpec,
    RoomRequest,
    TextBrief,
)
from app.modules.ai.floorplan.schemas.common import DEFAULT_LABEL
from app.modules.ai.floorplan.units import CM_PER_FT, CM_PER_M, to_cm
from app.modules.ai.llm.client import LLMClient, LLMError

logger = logging.getLogger("construtiva.ai.floorplan")

BEDROOM_TYPES = ("master_bedroom", "bedroom")
HOME_PURPOSES = (None, "residential", "rental")


@dataclass
class ParseResult:
    brief: Brief
    warnings: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # required before generating

    @property
    def ready(self) -> bool:
        return not self.missing


def read_text(prompt: str, llm: LLMClient | None) -> tuple[TextBrief, list[str]]:
    text = prompt.strip()
    if not text:
        return TextBrief(), []
    if llm is None:
        return TextBrief(), [
            "The description could not be read (AI is not configured); "
            "only the form values were used."
        ]
    try:
        tb = llm.structured(
            system=load_prompt("brief_parser"),
            user=json.dumps({"description": text}, ensure_ascii=False),
            schema=TextBrief,
            task="brief_parser",
        )
        return tb, []
    except LLMError as e:
        logger.warning("brief parser: LLM failed, using the form only: %s", e)
        return TextBrief(), [
            "The description could not be read automatically just now; only the form values "
            "were used. Check the summary below, or try again."
        ]


def parse_brief(form: BriefForm, llm: LLMClient | None = None) -> ParseResult:
    tb, warnings = read_text(form.prompt, llm)
    conflicts: list[Conflict] = []
    unknowns: list[str] = []
    assumptions: list[str] = []

    def pick(name: str, form_v, text_v):
        """The description wins when it states a value; the form fills the rest."""
        if text_v not in (None, ""):
            if form_v not in (None, "") and text_v != form_v:
                conflicts.append(
                    Conflict(field=name, form_value=str(form_v), text_value=str(text_v))
                )
            return text_v
        return form_v if form_v != "" else None

    # ------------------------------------------------------------------ plot
    plot, plot_notes = _plot(form, tb, conflicts)
    assumptions += plot_notes
    if plot.width_cm is None:
        unknowns.append("plot size")

    # --------------------------------------------------------------- purpose
    purpose = pick("purpose", form.purpose, tb.purpose)
    if purpose is None:
        unknowns.append("purpose")
        assumptions.append("Purpose not given: planned as a residential home.")

    # -------------------------------------------------------------- bedrooms
    text_bed_entries = [r for r in tb.rooms if r.type in BEDROOM_TYPES]
    text_bed_total = tb.bedrooms
    if text_bed_total is None and text_bed_entries:
        text_bed_total = sum(r.count for r in text_bed_entries)
    bedrooms = pick("bedrooms", form.bedrooms, text_bed_total)
    if bedrooms is None:
        unknowns.append("bedrooms")
    bed_rooms = _bedroom_entries(text_bed_entries, bedrooms)

    # ------------------------------------------------------------- bathrooms
    form_baths = form.bathrooms
    if (
        tb.bathrooms is None
        and form_baths is not None
        and form.bedrooms is not None
        and bedrooms != form.bedrooms
    ):
        # the form's bathroom count was for the form's (overridden) number of bedrooms
        assumptions.append(
            f"The form's {form_baths} bathrooms were for {form.bedrooms} bedrooms; "
            f"bathrooms were recalculated for {bedrooms}."
        )
        form_baths = None
    bathrooms = pick("bathrooms", form_baths, tb.bathrooms)
    if bathrooms is None:
        unknowns.append("bathrooms")

    # ----------------------------------------------------------- other rooms
    others: dict[str, RoomRequest] = {}
    for r in tb.rooms:
        if r.type in BEDROOM_TYPES:
            continue
        key = f"{r.type}:{(r.label or '').upper()}"
        if key in others:
            others[key] = others[key].model_copy(update={"count": max(others[key].count, r.count)})
        else:
            others[key] = r
    for t in form.extras:
        if t in BEDROOM_TYPES:
            continue
        if not any(k.startswith(f"{t}:") for k in others):
            others[f"{t}:"] = RoomRequest(type=t)
    # ---------------------------------------------------------------- the pool
    pool_layout = pick("pool layout", form.pool_layout, tb.pool_layout)
    pools = [k for k in others if k.startswith("pool:")]
    if pool_layout not in (None, "side") and not pools:
        others["pool:"] = RoomRequest(type="pool")
        pools = ["pool:"]
        assumptions.append("Added a swimming pool (the description places one).")
    if len(pools) > 1 or any(others[k].count > 1 for k in pools):
        for k in pools[1:]:
            del others[k]
        others[pools[0]] = others[pools[0]].model_copy(update={"count": 1})
        warnings.append("Only one swimming pool can be planned; one pool was planned.")
    if not pools:
        pool_layout = None
    if pool_layout == "two_block" and tb.covered_walkway:
        pool_layout = "u_shape"
        assumptions.append(
            "A covered walkway joins the two blocks along one side of the pool, so the "
            "house is U-shaped around it."
        )

    # "kitchen next to dining", "utility near the kitchen": a wish about a room means the
    # person wants that room, even when the reader did not list it separately
    for p in tb.preferences:
        if p.kind not in ("adjacent", "near", "on_side"):
            continue
        for t in (p.a, p.b):
            if t is None or t in BEDROOM_TYPES or t in ("bath", "shaft", "other"):
                continue
            if not any(k.startswith(f"{t}:") for k in others):
                others[f"{t}:"] = RoomRequest(type=t)
                if t not in ("living", "kitchen"):
                    name = DEFAULT_LABEL[t].lower()
                    assumptions.append(f"Added a {name} (the description mentions it).")
    if purpose in HOME_PURPOSES:
        for t in ("living", "kitchen"):
            if not any(k.startswith(f"{t}:") for k in others) and not (
                t == "living" and any(k.startswith("family_hall:") for k in others)
            ):
                others[f"{t}:"] = RoomRequest(type=t)
                assumptions.append(f"Added a {t} (every home needs one).")

    # -------------------------------------------------------------- the rest
    road_side = pick("road side", form.road_side, tb.road_side)
    if road_side is None:
        unknowns.append("road side")
        assumptions.append("Road side not given: entrance placed on the south side.")
    project = pick(
        "project name", form.project_name.strip() or None, (tb.project_name or "").strip() or None
    )
    owner = pick(
        "owner name", form.owner_name.strip() or None, (tb.owner_name or "").strip() or None
    )
    if tb.unsupported:
        warnings.append("Not supported in this tool and ignored: " + "; ".join(tb.unsupported))

    brief = Brief(
        plot=plot,
        purpose=purpose,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        rooms=bed_rooms + list(others.values()),
        road_side=road_side,
        project_name=project or "",
        owner_name=owner or "",
        preferences=tb.preferences,
        pool_layout=pool_layout,
        covered_walkway=tb.covered_walkway,
        notes=tb.notes,
        unknowns=unknowns,
        conflicts=conflicts,
        assumptions=assumptions,
    )
    return ParseResult(brief=brief, warnings=warnings, missing=missing_required(brief))


def missing_required(brief: Brief) -> list[str]:
    missing = []
    if brief.plot.width_cm is None or brief.plot.depth_cm is None:
        missing.append("plot size (width and depth, or area)")
    if brief.bedrooms is None and not any(r.type in BEDROOM_TYPES for r in brief.rooms):
        missing.append("number of bedrooms")
    return missing


def _plot(form: BriefForm, tb: TextBrief, conflicts: list[Conflict]) -> tuple[PlotSpec, list[str]]:
    notes: list[str] = []
    unit = form.unit
    text_unit = tb.plot_unit or form.unit
    text_dims = None
    if tb.plot_width and tb.plot_depth:
        text_dims = (to_cm(tb.plot_width, text_unit), to_cm(tb.plot_depth, text_unit))

    if form.plot_width and form.plot_depth:
        dims = (to_cm(form.plot_width, unit), to_cm(form.plot_depth, unit))
        same = text_dims is None or all(
            abs(a - b) / a <= 0.03 for a, b in zip(dims, text_dims, strict=True)
        )
        if same:
            return PlotSpec(width_cm=dims[0], depth_cm=dims[1], input_unit=unit), notes
        if text_dims:  # the description wins; the clash is shown on the confirmation card
            conflicts.append(
                Conflict(
                    field="plot size",
                    form_value=f"{form.plot_width:g} x {form.plot_depth:g} {unit}",
                    text_value=f"{tb.plot_width:g} x {tb.plot_depth:g} {text_unit}",
                )
            )
    if text_dims:
        if tb.plot_unit is None:
            notes.append(f"Plot unit not stated: read as {text_unit}.")
        return PlotSpec(width_cm=text_dims[0], depth_cm=text_dims[1], input_unit=text_unit), notes

    area_cm2 = None
    if form.plot_area:
        area_cm2 = form.plot_area * (CM_PER_FT if unit == "ft" else CM_PER_M) ** 2
    elif tb.plot_area:
        per = (
            CM_PER_FT
            if (tb.plot_area_unit or ("sqft" if unit == "ft" else "sqm")) == "sqft"
            else CM_PER_M
        )
        area_cm2 = tb.plot_area * per**2
    if area_cm2:
        rw, rd = DEFAULT_PLOT_RATIO
        width = math.sqrt(area_cm2 * rw / rd)
        depth = area_cm2 / width
        notes.append(
            f"Only the plot area was given, so a {rw}:{rd} (width:depth) shape was assumed. "
            "Enter the real width and depth for an accurate plan."
        )
        return (
            PlotSpec(
                width_cm=round(width), depth_cm=round(depth), input_unit=unit, shape_assumed=True
            ),
            notes,
        )
    return PlotSpec(input_unit=unit), notes


def _bedroom_entries(text_entries: list[RoomRequest], total: int | None) -> list[RoomRequest]:
    """Bedroom requests whose counts add up to the chosen total."""
    entries = sorted(text_entries, key=lambda r: r.type != "master_bedroom")
    if total is None:
        return entries
    current = sum(r.count for r in entries)
    while current > total and entries:  # trim plain bedrooms first, keep the master
        idx = max(range(len(entries)), key=lambda i: (entries[i].type == "bedroom", i))
        e = entries[idx]
        if e.count > 1:
            entries[idx] = e.model_copy(update={"count": e.count - 1})
        else:
            entries.pop(idx)
        current -= 1
    if current < total:
        entries.append(RoomRequest(type="bedroom", count=total - current))
    return entries
