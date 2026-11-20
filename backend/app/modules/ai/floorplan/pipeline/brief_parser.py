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
import re
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
        built_up_share=tb.built_up_share or form.built_up_share,
        setbacks=tb.setbacks,
        rules=tb.rules,
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
    elif brief.plot.stated_area_m2 and brief.plot.area_basis is None:
        missing.append(AREA_BASIS_QUESTION)
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
        basis = form.area_basis or tb.area_basis or area_basis_from_words(form.prompt)
        stated_m2 = area_cm2 / 10_000
        if basis == "plot":
            built, built_notes = built_up_from_words(form.prompt, unit, stated_m2, tb, form)
            notes += built_notes
        else:
            built = None
        plot_cm2 = area_cm2
        what = "plot"
        if basis == "built_up":
            share = built_up_share(form, tb)
            plot_cm2 = area_cm2 / share
            what = "built-up"
            notes.append(
                f"The {fmt_area_m2(stated_m2, unit)} is the built-up area; at {share:.0%} "
                f"built-up the plot is about {fmt_area_m2(plot_cm2 / 10_000, unit)}."
            )
        rw, rd = DEFAULT_PLOT_RATIO
        width = math.sqrt(plot_cm2 * rw / rd)
        depth = plot_cm2 / width
        notes.append(
            f"Only the {what} area was given, so a {rw}:{rd} (width:depth) plot shape was "
            "assumed. Enter the real width and depth for an accurate plan."
        )
        return (
            PlotSpec(
                width_cm=round(width / 5) * 5,
                depth_cm=round(depth / 5) * 5,
                input_unit=unit,
                shape_assumed=True,
                area_basis=basis,
                stated_area_m2=round(stated_m2, 2),
                built_up_m2=round(stated_m2, 2) if basis == "built_up" else built,
            ),
            notes,
        )
    return PlotSpec(input_unit=unit), notes


_BUILT_UP_WORDS = re.compile(
    r"\b(built[\s-]*up|covered|construction|constructed|floor|carpet|bua)\s*(area)?\b"
    r"|\bthe (house|villa|home) (is|of) \d",
    re.IGNORECASE,
)
_PLOT_WORDS = re.compile(r"\b(plot|land|site|lot)\b", re.IGNORECASE)


def area_basis_from_words(text: str) -> str | None:
    """'plot' or 'built_up' when the wording says which area was meant, else None.

    Only the last sentence that mentions an area decides, so an answer given after the
    question ("it is the built-up area") wins over the first description."""
    for sentence in reversed(re.split(r"[.\n!?]+", text or "")):
        built, plot = _BUILT_UP_WORDS.search(sentence), _PLOT_WORDS.search(sentence)
        if built and not plot:
            return "built_up"
        if plot and not built:
            return "plot"
        if built and plot:  # "5000 sq ft plot with 3500 sq ft built-up": a plot size
            return "plot"
    return None


_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
_AREA_UNIT = (
    r"(sq\.?\s*(?:ft|feet|foot|m|mt|mtr|meters?|metres?)\b|square\s+(?:feet|foot|meters?|metres?)"
    r"|ft\.?\s*(?:²|2|sq)|feet\s*(?:²|2)|m\s*²|m2\b|sqft\b|sqm\b)?"
)
_AT_LEAST = r"(at\s*least|atleast|min(?:imum)?\.?|not\s+less\s+than|more\s+than)?"
_BUILT_WORD = r"(?:built|build|buil)[\s-]*up(?:\s+area)?|bua|covered\s+area|construction\s+area"
_BUILT_AFTER = re.compile(
    rf"\b(?:{_BUILT_WORD})\s*(?:of|is|=|:|should\s+be|must\s+be|to\s+be|around|about)?\s*"
    rf"{_AT_LEAST}\s*(?:of\s+)?{_NUM}\s*{_AREA_UNIT}",
    re.IGNORECASE,
)
_BUILT_BEFORE = re.compile(
    rf"{_AT_LEAST}\s*{_NUM}\s*{_AREA_UNIT}\s*(?:of\s+)?(?:{_BUILT_WORD})\b",
    re.IGNORECASE,
)


def stated_built_up(text: str, unit: str) -> tuple[float, bool] | None:
    """The built-up area a description states beside the plot area, in m², and whether it
    is a minimum ("at least 3000 sq ft built-up"). None when it states none."""
    for pattern in (_BUILT_AFTER, _BUILT_BEFORE):
        m = pattern.search(text or "")
        if not m:
            continue
        at_least, number, unit_words = m.group(1), m.group(2), (m.group(3) or "").lower()
        value = float(number.replace(",", ""))
        metric = bool(re.search(r"\bm\b|m²|m2|sqm|met|mtr|mt\b", unit_words))
        feet = bool(re.search(r"ft|feet|foot", unit_words))
        per = CM_PER_M if metric or (not feet and unit == "m") else CM_PER_FT
        m2 = value * per**2 / 10_000
        if m2 > 5:
            return m2, bool(at_least)
    return None


def built_up_from_words(
    text: str, unit: str, plot_m2: float, tb: TextBrief, form: BriefForm
) -> tuple[float | None, list[str]]:
    """The person's own built-up area when the description states one beside the plot.

    The person's number wins over the usual share band. A minimum ("at least 3000 sq ft")
    that the default share already exceeds keeps the default (the wish is met) and says so."""
    found = stated_built_up(text, unit)
    if found is None:
        return None, []
    m2, at_least = found
    if at_least:
        default_m2 = built_up_share(form, tb) * plot_m2
        if default_m2 >= m2:
            return None, [
                f"Built-up area at least {fmt_area_m2(m2, unit)}: planned about "
                f"{fmt_area_m2(default_m2, unit)} ({default_m2 / plot_m2:.0%} of the plot)."
            ]
    return round(m2, 2), [f"Built-up area {fmt_area_m2(m2, unit)}, as you asked."]


def built_up_share(form: BriefForm, tb: TextBrief) -> float:
    """The built-up share of the plot: the person's (text, then form), else the setting."""
    from app.modules.ai.floorplan.settings import get_settings

    return tb.built_up_share or form.built_up_share or get_settings().built_up_share


def fmt_area_m2(m2: float, unit: str) -> str:
    if unit == "ft":
        return f"{m2 * 10.7639:,.0f} sq ft"
    return f"{m2:,.0f} m²"


AREA_BASIS_QUESTION = (
    "Is the area you gave the plot area or the built-up area? Choose one on the card "
    "(plot or built-up) and confirm."
)


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
