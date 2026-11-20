"""Room program: target areas and adjacency wishes for the fixed room list.

The LLM sizes the rooms code derived from the brief (ids are fixed; it cannot add or
drop rooms) and suggests adjacencies. Code then:
  - enforces minimum sizes and takes zones / attachments from rules, not the LLM
  - adds the person's stated preferences as adjacencies (they never depend on the LLM)
  - scales targets to the plot so the layout has a realistic budget
On a retry the validator's exact errors are sent back. Without an LLM, typical sizes
are used and adjusted by simple rules.
"""

import json
import logging
import re

from pydantic import BaseModel, Field

from app.modules.ai.floorplan.pipeline.pool_layouts import (
    Choice,
    apply_layout,
    pool_target_m2,
)
from app.modules.ai.floorplan.pipeline.requirements import ReqRoom, expand_rooms
from app.modules.ai.floorplan.prompts import load_prompt
from app.modules.ai.floorplan.rules import (
    AREA_FLEXIBLE_TYPES,
    COURTYARD_PLOT_SHARE,
    GARDEN_MIN_SPARE,
    MIN_ROOM,
    PARKING_PER_CAR_M2,
    POOL_PLOT_SHARE_MAX,
    PROGRAM_PLOT_SHARE,
    ROOM_SCALE_UP_MAX,
    TYPICAL_ROOM_M2,
)
from app.modules.ai.floorplan.schemas.brief import Brief
from app.modules.ai.floorplan.schemas.common import ZONE_BY_TYPE
from app.modules.ai.floorplan.schemas.program import Adjacency, ProgramRoom, RoomProgram
from app.modules.ai.llm.client import LLMClient, LLMError

logger = logging.getLogger("construtiva.ai.floorplan")

OPEN_TYPES = ("garden", "lawn", "courtyard", "parking", "driveway", "dock", "balcony", "pool", "deck")


class DraftRoom(BaseModel):
    id: str
    target_area_m2: float = Field(gt=0)
    label: str | None = None


class ProgramDraft(BaseModel):
    rooms: list[DraftRoom]
    adjacency: list[Adjacency] = Field(default_factory=list)
    notes: str = ""


def _min_area(t: str) -> float:
    return max(MIN_ROOM[t].area_m2, (MIN_ROOM[t].short_side_cm / 100) ** 2)


def _ask_llm(
    brief: Brief,
    reqs: list[ReqRoom],
    llm: LLMClient,
    feedback: list[str] | None,
    previous: RoomProgram | None,
) -> ProgramDraft:
    payload = {
        "brief": {
            "purpose": brief.purpose,
            "bedrooms": brief.bedrooms,
            "bathrooms": brief.bathrooms,
            "road_side": brief.road_side,
            "preferences": [p.model_dump(exclude_none=True) for p in brief.preferences],
            "notes": brief.notes,
        },
        "plot": {
            "width_m": brief.plot.width_cm / 100,
            "depth_m": brief.plot.depth_cm / 100,
            "usable_area_m2": round(brief.plot.width_cm * brief.plot.depth_cm / 10_000, 1),
        },
        "rooms": [
            {
                "id": r.id,
                "type": r.type,
                "default_label": r.label,
                "min_area_m2": round(_min_area(r.type), 1),
                "attached_to": r.attached_to,
            }
            for r in reqs
        ],
    }
    if previous is not None:
        payload["previous_targets"] = {r.id: r.target_area_m2 for r in previous.rooms}
    if feedback:
        payload["layout_errors"] = feedback[:20]
    return llm.structured(
        system=load_prompt("room_program"),
        user=json.dumps(payload, ensure_ascii=False),
        schema=ProgramDraft,
        task="room_program",
    )


def build_program(
    brief: Brief,
    llm: LLMClient | None = None,
    *,
    feedback: list[str] | None = None,
    previous: RoomProgram | None = None,
    pool: Choice | None = None,
) -> tuple[RoomProgram, list[str]]:
    """`pool` is the pool layout to plan for (from pool_layouts.layout_chain); None means
    the brief's own request, or beside the house."""
    reqs, notes = expand_rooms(brief)
    pool = pool or Choice(brief.pool_layout or "side")
    reqs, pool_notes = apply_layout(reqs, pool)
    notes += pool_notes
    warnings: list[str] = []
    draft: ProgramDraft | None = None
    if llm is not None:
        try:
            draft = _ask_llm(brief, reqs, llm, feedback, previous)
        except LLMError as e:
            logger.warning("room program: LLM failed, using typical sizes: %s", e)
            warnings.append("AI room sizing was unavailable; typical room sizes were used.")
    by_id = {d.id: d for d in draft.rooms} if draft else {}

    prev_targets = {p.id: p.target_area_m2 for p in previous.rooms} if previous else {}
    targets: dict[str, float] = {}
    labels: dict[str, str] = {}
    for r in reqs:
        d = by_id.get(r.id)
        base = d.target_area_m2 if d else prev_targets.get(r.id, TYPICAL_ROOM_M2[r.type])
        targets[r.id] = max(_min_area(r.type), base)
        label = (d.label or "").strip().upper() if d and d.label else ""
        labels[r.id] = re.sub(r"[^A-Z0-9 ./&-]", "", label)[:24] or r.label

    if feedback and draft is None:
        _apply_feedback_rules(targets, reqs, feedback)

    added_garden = _fit_to_plot(targets, reqs, brief, pool)
    if added_garden:
        reqs = reqs + [ReqRoom("garden_1", "garden", "GARDEN")]
        labels["garden_1"] = "GARDEN"
        notes.append("Spare plot area is shown as a GARDEN.")

    rooms = [
        ProgramRoom(
            id=r.id,
            type=r.type,
            label=labels[r.id],
            target_area_m2=round(targets[r.id], 2),
            zone=ZONE_BY_TYPE[r.type],
            attached_to=r.attached_to,
            block=r.block,  # type: ignore[arg-type]
        )
        for r in reqs
    ]
    has_pool = any(r.type == "pool" for r in reqs)
    program = RoomProgram(
        rooms=rooms,
        adjacency=_adjacency(brief, reqs, draft),
        entrance_side=brief.road_side,
        pool_layout=pool.layout if has_pool else None,  # type: ignore[arg-type]
        pool_axis=pool.axis if has_pool else None,
    )
    return program, warnings + notes


def _first_of(reqs: list[ReqRoom], t: str) -> str | None:
    if t in ("bedroom", "master_bedroom"):
        t_list = (
            ("master_bedroom", "bedroom")
            if t == "master_bedroom"
            else ("bedroom", "master_bedroom")
        )
    else:
        t_list = (t,)
    for tt in t_list:
        for r in reqs:
            if r.type == tt:
                return r.id
    return None


def _adjacency(brief: Brief, reqs: list[ReqRoom], draft: ProgramDraft | None) -> list[Adjacency]:
    ids = {r.id for r in reqs}
    attached = {(r.id, r.attached_to) for r in reqs if r.attached_to}
    pairs: dict[tuple[str, str], int] = {}

    def add(a: str | None, b: str | None, w: int) -> None:
        if not a or not b or a == b or a not in ids or b not in ids:
            return
        if (a, b) in attached or (b, a) in attached:
            return
        key = tuple(sorted((a, b)))
        pairs[key] = max(pairs.get(key, 0), max(1, min(10, w)))

    for p in brief.preferences:
        if p.kind in ("adjacent", "near") and p.b:
            add(_first_of(reqs, p.a), _first_of(reqs, p.b), 8 if p.kind == "adjacent" else 5)
    add(_first_of(reqs, "kitchen"), _first_of(reqs, "dining"), 5)
    add(_first_of(reqs, "dining"), _first_of(reqs, "living"), 3)
    if draft:
        for a in draft.adjacency:
            add(a.a, a.b, a.weight)
    return [Adjacency(a=a, b=b, weight=w) for (a, b), w in sorted(pairs.items())]


def _fit_to_plot(
    targets: dict[str, float], reqs: list[ReqRoom], brief: Brief, pool: Choice | None = None
) -> bool:
    """Size the program to the plot. Returns True if a garden was added.

    Parking and courtyard get sensible targets (they are capped in the layout too), the
    fixed-size rooms are scaled into what is left (up to ROOM_SCALE_UP_MAX on a large
    plot), and any space still spare goes to a garden, the one open area that absorbs
    leftovers. Rooms are never left small while open space takes the plot.
    """
    plot_m2 = brief.plot.width_cm * brief.plot.depth_cm / 10_000
    for r in reqs:
        if r.type == "parking":
            targets[r.id] = min(max(targets[r.id], PARKING_PER_CAR_M2[0]), PARKING_PER_CAR_M2[1])
        elif r.type == "courtyard":
            m = _min_area(r.type)
            lo_c, hi_c = (max(m, share * plot_m2) for share in COURTYARD_PLOT_SHARE)
            targets[r.id] = min(max(targets[r.id], lo_c), hi_c)
        elif r.type in ("pool", "deck"):
            cap = max(_min_area(r.type), POOL_PLOT_SHARE_MAX * plot_m2)
            special = (
                pool_target_m2(pool, brief.plot.width_cm, brief.plot.depth_cm, brief.road_side)
                if r.type == "pool" and pool
                else None
            )
            if special is not None:
                targets[r.id] = special
            targets[r.id] = min(max(targets[r.id], _min_area(r.type)), cap)
    open_need = sum(targets[r.id] for r in reqs if r.type in OPEN_TYPES)
    lo = PROGRAM_PLOT_SHARE[0] * plot_m2 - open_need
    hi = max(lo, PROGRAM_PLOT_SHARE[1] * plot_m2 - open_need)
    fixed = [r for r in reqs if r.type not in AREA_FLEXIBLE_TYPES and r.type not in OPEN_TYPES]
    total = sum(targets[r.id] for r in fixed)
    if total <= 0:
        return False
    if total > hi:
        factor = max(hi, 0) / total
    elif total < lo:
        factor = min(lo / total, ROOM_SCALE_UP_MAX)
    else:
        factor = 1.0
    for r in fixed:
        targets[r.id] = max(_min_area(r.type), targets[r.id] * factor)
    fixed_total = sum(targets[f.id] for f in fixed)
    for r in reqs:
        if r.type in ("lobby", "passage"):
            targets[r.id] = max(_min_area(r.type), 0.07 * fixed_total)
    circulation = sum(targets[r.id] for r in reqs if r.type in ("lobby", "passage"))
    spare = plot_m2 - (fixed_total + circulation) * 1.08 - open_need
    has_garden = any(r.type == "garden" for r in reqs)
    if not has_garden and spare > GARDEN_MIN_SPARE * plot_m2:
        targets["garden_1"] = max(6.0, spare * 0.5)
        return True
    return False


_ROOM_IN_ERROR = re.compile(r"^(MIN_SIDE|MIN_AREA|AREA_MISMATCH): (\S+) ")


def _apply_feedback_rules(
    targets: dict[str, float], reqs: list[ReqRoom], feedback: list[str]
) -> None:
    """Fallback without an LLM: nudge sizes using the validator's error codes."""
    touched = False
    for line in feedback:
        m = _ROOM_IN_ERROR.match(line)
        if m and m.group(2) in targets:
            code, rid = m.groups()
            factor = 1.15 if code in ("MIN_SIDE", "MIN_AREA") else 1.0
            targets[rid] *= factor
            touched = True
    if not touched or any(not _ROOM_IN_ERROR.match(f) for f in feedback):
        for r in reqs:  # rooms did not fit together: give the solver more slack
            if r.type not in AREA_FLEXIBLE_TYPES:
                targets[r.id] = max(_min_area(r.type), targets[r.id] * 0.92)
