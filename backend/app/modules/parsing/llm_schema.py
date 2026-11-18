"""What the plan parser asks a model for, and the checks its reply must pass.

`LLMPlanDraft` has the same field names as PlanJSON but is looser where the normaliser
fixes things anyway (any unit, missing defaults, either `offset` or `position` for an
opening). It is strict where a mistake would silently bend the geometry: coordinates must
be real numbers, and every opening must sit on a wall that exists.

`check_draft` returns the reply's problems as plain sentences. The parser sends them back
to the model when it asks for a corrected reply.
"""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.modules.parsing.normalise import clean_polygon, signed_area, stated_area_m2, unit_scale

MAX_ERRORS_REPORTED = 40

# Drawn extent / reported overall size must fall in this range on both axes.
OVERALL_SIZE_TOLERANCE = (0.85, 1.15)
# Median of (drawn room area / area printed in the room's label) must fall in this range.
# It is wide because labels give clear inside sizes and L-shaped rooms are smaller than
# the rectangle their label describes.
ROOM_AREA_RATIO_RANGE = (0.70, 1.40)
MIN_LABELLED_ROOMS_FOR_SCALE_CHECK = 3

Number = Annotated[float, Field(allow_inf_nan=False)]
DraftPoint = Annotated[list[Number], Field(min_length=2, max_length=2)]


class _Draft(BaseModel):
    model_config = ConfigDict(extra="ignore")


class DraftWall(_Draft):
    id: str | int
    start: DraftPoint
    end: DraftPoint
    thickness: Number | None = None
    kind: str | None = None
    is_exterior: bool | None = None
    inferred: bool = False


class DraftOpening(_Draft):
    id: str | int
    wall_id: str | int
    type: str
    offset: Number | None = None
    position: DraftPoint | None = None
    width: Number | None = None
    height: Number | None = None
    sill: Number | None = None
    sill_height: Number | None = None
    inferred: bool = False


class DraftColumn(_Draft):
    id: str | int
    position: DraftPoint
    width: Number | None = None
    depth: Number | None = None


class DraftRoom(_Draft):
    id: str | int
    name: str | None = None
    kind: str | None = None
    polygon: list[DraftPoint] = Field(min_length=3)
    height_m: Number | None = None
    is_double_height_void: bool = False


class DraftLevel(_Draft):
    index: int | None = None
    name: str | None = None
    # Overall size of the floor plan as printed on the drawing, in the reply's units.
    # Used only to check the scale of the reply; it is not part of PlanJSON.
    overall_width: Number | None = None
    overall_depth: Number | None = None
    elevation: Number | None = None
    wall_height: Number | None = None
    wall_height_source: str | None = None
    rooms: list[DraftRoom] = Field(default_factory=list)
    walls: list[DraftWall] = Field(default_factory=list)
    openings: list[DraftOpening] = Field(default_factory=list)
    columns: list[DraftColumn] = Field(default_factory=list)


class LLMPlanDraft(_Draft):
    # False when the pages show no floor plan at all; `levels` is then empty.
    floor_plan_found: bool = True
    units: str = "m"
    building_type: str | None = None
    scale_source: str | None = None
    project_title: str | None = None
    subject: str | None = None
    client: str | None = None
    architect: str | None = None
    levels: list[DraftLevel] = Field(default_factory=list)


DRAFT_JSON_SCHEMA: dict[str, Any] = LLMPlanDraft.model_json_schema()


def _path(loc: tuple) -> str:
    out = ""
    for part in loc:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out or "reply"


def _semantic_errors(draft: LLMPlanDraft, min_rooms: int) -> list[str]:
    errors: list[str] = []
    if not draft.levels:
        return ["levels: return one entry for each floor plan that is drawn."]
    scale = unit_scale(draft.units)
    if scale is None:
        errors.append(f'units: {draft.units!r} is not a known unit; use "m" and give metres.')
        scale = 1.0

    for li, level in enumerate(draft.levels):
        wall_ids: set[str] = set()
        for wi, wall in enumerate(level.walls):
            wid = str(wall.id)
            if wid in wall_ids:
                errors.append(
                    f"levels[{li}].walls[{wi}].id: {wid!r} is used by more than one wall."
                )
            wall_ids.add(wid)
            if wall.start == wall.end:
                errors.append(f"levels[{li}].walls[{wi}]: start and end are the same point.")
        for oi, opening in enumerate(level.openings):
            where = f"levels[{li}].openings[{oi}]"
            host = str(opening.wall_id)
            if host not in wall_ids:
                errors.append(f"{where}.wall_id: {host!r} is not the id of a wall in this level.")
            if opening.offset is None and opening.position is None:
                errors.append(
                    f"{where}: give `offset` (metres from the wall's start to the centre)."
                )
        for ri, room in enumerate(level.rooms):
            where = f"levels[{li}].rooms[{ri}]"
            if "<" in (room.name or "") and ">" in (room.name or ""):
                errors.append(
                    f"{where}.name: this is the prompt's placeholder, not a label from the drawing."
                )
            points = [list(p) for p in room.polygon]
            if clean_polygon(points, scale) is None:
                errors.append(
                    f"{where}.polygon: needs at least 3 different corners that enclose an area."
                )

    usable = sum(
        1
        for room in draft.levels[0].rooms
        if clean_polygon([list(p) for p in room.polygon], scale) is not None
    )
    if usable < max(min_rooms, 1):
        errors.append(
            f"levels[0].rooms: only {usable} usable room(s); the drawing must yield at least "
            f"{max(min_rooms, 1)}. Extract every room of the floor plan."
        )
    return errors


def _extent(level: DraftLevel, scale: float) -> tuple[float, float] | None:
    """(width, depth) in metres of everything drawn on a level."""
    xs: list[float] = []
    ys: list[float] = []
    for wall in level.walls:
        for x, y in (wall.start, wall.end):
            xs.append(x * scale)
            ys.append(y * scale)
    for room in level.rooms:
        for x, y in room.polygon:
            xs.append(x * scale)
            ys.append(y * scale)
    if not xs:
        return None
    return max(xs) - min(xs), max(ys) - min(ys)


def scale_concerns(draft: LLMPlanDraft) -> list[str]:
    """Signs that a structurally valid reply is drawn at the wrong size.

    Two independent checks per level, both against what the drawing itself prints:
    the extent of the geometry against the overall dimensions the model reported, and
    the drawn area of each room against the size in its label.
    """
    concerns: list[str] = []
    scale = unit_scale(draft.units) or 1.0
    low, high = OVERALL_SIZE_TOLERANCE
    for li, level in enumerate(draft.levels):
        extent = _extent(level, scale)
        if extent and level.overall_width and level.overall_depth:
            stated = (level.overall_width * scale, level.overall_depth * scale)
            if stated[0] > 0 and stated[1] > 0:
                ratios = (extent[0] / stated[0], extent[1] / stated[1])
                if not all(low <= r <= high for r in ratios):
                    drawn = f"{extent[0]:.2f} x {extent[1]:.2f} m"
                    reported = f"{stated[0]:.2f} x {stated[1]:.2f} m"
                    concerns.append(
                        f"levels[{li}]: the coordinates span {drawn}, "
                        f"but the overall size you reported is {reported}. "
                        "The outer boundary must run from (0, 0) to (overall width, overall depth)."
                    )

        labelled: list[tuple[float, str, float, float]] = []
        for room in level.rooms:
            stated_area = stated_area_m2(room.name)
            polygon = clean_polygon([list(p) for p in room.polygon], scale)
            if stated_area and polygon:
                drawn = abs(signed_area(polygon))
                labelled.append((drawn / stated_area, room.name or "", drawn, stated_area))
        if len(labelled) >= MIN_LABELLED_ROOMS_FOR_SCALE_CHECK:
            labelled.sort()
            median = labelled[len(labelled) // 2]
            if not ROOM_AREA_RATIO_RANGE[0] <= median[0] <= ROOM_AREA_RATIO_RANGE[1]:
                concerns.append(
                    f"levels[{li}]: rooms are drawn at about {median[0]:.0%} of the area their "
                    f"labels state (for example '{median[1]}' is drawn as {median[2]:.2f} m2 but "
                    f"its label gives {median[3]:.2f} m2). Convert each printed dimension to "
                    "metres and size every room from its printed dimensions."
                )
    return concerns


def check_draft(reply: Any, min_rooms: int = 1) -> tuple[LLMPlanDraft | None, list[str], list[str]]:
    """(draft, [], concerns) when the reply is usable, else (None, problems, []).

    `problems` make a reply unusable. `concerns` (see `scale_concerns`) do not: the
    parser asks the model to fix them while it has attempts left, and otherwise keeps
    the reply, whose doubtful scale then shows up in the plan's warnings.
    """
    try:
        draft = LLMPlanDraft.model_validate(reply)
    except ValidationError as e:
        problems = [f"{_path(err['loc'])}: {err['msg']}" for err in e.errors()]
        return None, problems[:MAX_ERRORS_REPORTED], []
    if not draft.floor_plan_found:
        return draft, [], []  # the caller reports this; there is nothing to repair
    problems = _semantic_errors(draft, min_rooms)
    if problems:
        return None, problems[:MAX_ERRORS_REPORTED], []
    return draft, [], scale_concerns(draft)
