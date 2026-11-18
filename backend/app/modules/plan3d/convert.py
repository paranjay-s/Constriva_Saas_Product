"""PlanJSON (ours, metres) -> PlanTo3D's plan JSON (feet), for plans its detector cannot read.

PlanTo3D normally reads a CAD PDF itself. When it cannot (a scan, a photo, a drawing in a
style it does not know), our AI parser reads the PDF into a PlanJSON, and a plan made by our
own floor plan generator is a PlanJSON from the start. This module turns either into the
document PlanTo3D's review page opens and its builder builds, so the rest of the 3D flow is
the same whoever read the drawing.

It is a pure function: no file, no network, no settings. It never raises on a plan that
validates against `plans/schemas.py`; a plan it cannot use at all comes back with
`plan=None` and the reason, so the caller can fall back to tracing the walls by hand.

The two formats, side by side (docs/08-3d.md has the full field list):

    PlanJSON                                 PlanTo3D
    metres                                   feet
    y grows down the page                    y grows up the page
    origin wherever the reader put it        origin at the lower-left corner of the walls
    wall = centre line + thickness           wall = rectangle [x0, x1, y0, y1, low]
    opening = wall id + offset + width       opening = rectangle across its wall + axis
    room = polygon                           room = a union of rectangles + a type
    walls at any angle                       axis-aligned rectangles only

PlanTo3D has no slanted walls. A wall within 5 degrees of an axis is straightened; a truly
slanted one becomes a run of short steps (or is left out, `diagonal="skip"`), and its
openings are dropped. Every such approximation is written to `ConvertResult.notes`.
"""

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

FT_PER_M = 1 / 0.3048
# PlanJSON says metres. The other units cost nothing to accept and save a failed job when a
# stored document predates the rule.
_TO_FT = {"m": FT_PER_M, "cm": FT_PER_M / 100, "mm": FT_PER_M / 1000, "ft": 1.0, "in": 1 / 12}

# ---------------------------------------------------------------- PlanTo3D's vocabulary
# web/edit.js TYPES: the room types the review page offers and the builder has a floor for.
PLANTO3D_TYPES = (
    "bedroom", "toilet", "kitchen", "living", "dining", "puja", "wash", "store", "study",
    "passage", "balcony", "garden", "open", "parking", "yard", "stair", "room", "duct", "dress",
)  # fmt: skip
OUTDOOR = frozenset({"open", "garden", "parking", "balcony", "yard"})  # detect.py OUTDOOR
INDOOR = frozenset(  # blender/gen.py INDOOR: rooms with a ceiling, a lamp and furniture
    {
        "bedroom", "toilet", "kitchen", "living", "dining", "puja", "study", "store",
        "passage", "room", "wash", "dress",
    }
)  # fmt: skip

# detect.py ROOM_TYPES, copied so a room is typed the same way whoever read the drawing.
# First match wins; a keyword of three letters or more also matches as a prefix.
ROOM_TYPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("toilet", ("TOI", "TOILET", "BATH", "W.C", "WC", "WASHROOM", "LAV", "POWDER")),
    ("bedroom", ("BED", "BEDROOM", "BEDRM", "B.R", "M.BED", "MASTER", "GUEST", "KIDS")),
    ("kitchen", ("KIT", "KITCHEN", "PANTRY")),
    ("dining", ("DIN", "DINING")),
    ("living", ("LIV", "LIVING", "DRG", "DRAWING", "LOUNGE", "HALL", "FAMILY", "SITTING")),
    ("puja", ("PUJA", "POOJA", "MANDIR", "PRAYER", "TEMPLE")),
    ("wash", ("WASH", "UTILITY", "LAUNDRY", "DRY")),
    ("dress", ("DRESS", "DRESSING", "WARDROBE", "W.I.C")),
    ("store", ("STORE", "STR", "STORAGE")),
    ("study", ("STUDY", "OFFICE", "LIBRARY")),
    ("passage", ("PASSAGE", "LOBBY", "CORRIDOR", "FOYER", "ENTRANCE", "PASS")),
    (
        "balcony",
        ("BALCONY", "SITOUT", "SIT-OUT", "VERANDAH", "VERANDA", "TERRACE", "DECK", "PORCH"),
    ),
    ("garden", ("LAWN", "GARDEN", "COURTYARD", "OTS")),
    ("open", ("OPEN", "SHAFT", "DUCT", "CUTOUT", "VOID")),
    ("parking", ("PARKING", "CAR", "GARAGE")),
    ("stair", ("STAIR", "STAIRCASE", "UP", "DN")),
)

# The floor plan generator's room types (ai/floorplan/schemas/common.py RoomType), which it
# stores as `room.tag`. PlanTo3D has no pool: it becomes an open paved yard that keeps its name.
GENERATOR_TAGS = {
    "bedroom": "bedroom", "master_bedroom": "bedroom", "maid_room": "bedroom",
    "living": "living", "family_hall": "living", "dining": "dining", "kitchen": "kitchen",
    "bath": "toilet", "toilet": "toilet", "dress": "dress", "store": "store", "study": "study",
    "lobby": "passage", "passage": "passage", "foyer": "passage", "utility": "wash",
    "stair": "stair", "courtyard": "garden", "garden": "garden", "balcony": "balcony",
    "parking": "parking", "pool": "yard", "deck": "balcony", "shaft": "open", "other": "room",
}  # fmt: skip
# plans/room_types.py BoqType: what the parser decided a room is used for.
BOQ_TYPES = {
    "BATH": "toilet", "KITCHEN": "kitchen", "LAUNDRY": "wash", "CIRC": "passage",
    "LIVING": "living", "DINING": "dining", "STORE": "store", "BED": "bedroom",
    "STUDY": "study", "OTHER": "room",
}  # fmt: skip
ROOM_KINDS = {"indoor": "room", "semi_open": "balcony", "outdoor": "yard", "void": "open"}

# ---------------------------------------------------------------- conversion rules (feet)
EXTERIOR_WALL_FT = 0.75  # 9 inch brick wall, used when a wall has no thickness
INTERIOR_WALL_FT = 0.375  # 4.5 inch partition (PlanTo3D assumes the same)
MIN_WALL_FT, MAX_WALL_FT = 0.25, 2.0  # thickness is brought inside this range
MIN_WALL_LENGTH_FT = 0.25  # shorter centre lines are dropped
STRAIGHTEN_DEG = 5.0  # a wall this close to an axis is straightened onto it
STRAIGHT_FT = 0.07  # ... and one that is off by less than this is not even mentioned
JOIN_FT = 0.5  # a wall end this close to a crossing wall is joined to it
EXTEND_FT = 5.0  # a wall lengthened to hold its openings runs on to a crossing wall this near
MOVED_FT = 0.5  # an opening slid along its wall by more than this is mentioned
STEP_FT = 1.0  # length of one step of a slanted wall
MIN_OPENING_FT = 1.0  # an opening narrower than this after fitting is dropped
MIN_ROOM_SQFT = 2.0  # detect.py drops regions smaller than this too
MIN_RECT_FT = 0.1  # slivers left when walls are cut out of a room
SLANT_CELL_FT = 0.5  # grid used to cut a room with slanted edges into rectangles
PROBE_FT = 0.75  # how far beside a wall its neighbouring rooms are looked up
DEFAULT_FLOOR_HEIGHT_FT, MIN_FLOOR_HEIGHT_FT, MAX_FLOOR_HEIGHT_FT = 10.0, 8.0, 14.0
SLAB_FT = 0.5
# Without a registration the page image is not lined up with the plan. This scale (1 inch
# on paper = 6 ft, the sample plan's) only gives the review page a finite number to draw with.
UNREGISTERED_PT_PER_FT = 12.0

# ---------------------------------------------------------------- plausibility thresholds
MIN_WALLS = 4  # a closed outline needs four
MIN_SIDE_FT, MAX_SIDE_FT = 8.0, 300.0  # outer size of one floor
MIN_MEDIAN_WALL_FT, MAX_MEDIAN_WALL_FT = 0.15, 2.5  # outside this the scale is wrong
MAX_ROOM_SQFT = 5000.0
MAX_LEAK = 0.2  # share of the indoor floor area that may be reachable from outside
MAX_OUTSIDE = 0.5  # share of an indoor room that may lie outside the walls
MIN_COVER = 0.15  # the rooms together must cover this share of the walls' bounding box
MAX_OVERLAP = 1.2  # indoor room area may not exceed the bounding box by more than this

_FLOOR_NAMES = ("Ground Floor", "First Floor", "Second Floor", "Third Floor", "Fourth Floor")
_REAL_SCALES = {"dimension_label", "scale_bar", "stated_scale", "scale_text", "user_reference"}

Rect = list[float]


@dataclass(frozen=True)
class ConvertResult:
    """`plan` is PlanTo3D's plan JSON, or None with `reason` when nothing could be made.

    `notes` say what was dropped or approximated, for the person reviewing the plan.
    `problems` are the reasons the result looks implausible (see `check_plausible`);
    a plan with problems can still be opened for review, but should not be built unseen.
    """

    plan: dict[str, Any] | None
    notes: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def usable(self) -> bool:
        return self.plan is not None

    @property
    def plausible(self) -> bool:
        return self.plan is not None and not self.problems


@dataclass
class _Wall:
    """An axis-aligned wall on its centre line, in feet, y up."""

    wall_id: str
    horizontal: bool
    c: float  # the fixed coordinate (y of a horizontal wall)
    a0: float  # centre line, low end
    a1: float
    t: float
    start: float = 0.0  # where the centre line starts and ends as drawn: offsets run this way
    end: float = 0.0
    drawn: float = 0.0  # its length as drawn, before it was lengthened for its openings
    reach: float = 0.0  # how far along it its farthest opening ends
    column: bool = False
    lo: float = 0.0  # the rectangle's ends, after joining to crossing walls
    hi: float = 0.0
    inner0: float = 0.0  # where an opening may start: the inner face of a crossing wall
    inner1: float = 0.0
    taken: list[tuple[float, float]] = field(default_factory=list)

    def a_low(self) -> float:
        return min(self.start, self.end)

    def a_high(self) -> float:
        return max(self.start, self.end)

    def rect(self) -> Rect:
        half = self.t / 2
        if self.horizontal:
            return [self.lo, self.hi, self.c - half, self.c + half]
        return [self.c - half, self.c + half, self.lo, self.hi]


# ---------------------------------------------------------------- small helpers
def _num(value: Any) -> float | None:
    """A finite number, or None. Pydantic accepts NaN and infinity as floats; geometry cannot."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) and abs(number) < 1e7 else None


def _text(value: Any) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list | tuple) else []


def _contains(r: Sequence[float], x: float, y: float) -> bool:
    return r[0] <= x <= r[1] and r[2] <= y <= r[3]


def _area(r: Sequence[float]) -> float:
    return max(0.0, r[1] - r[0]) * max(0.0, r[3] - r[2])


def _is_horizontal(r: Sequence[float]) -> bool:
    return (r[1] - r[0]) >= (r[3] - r[2])  # detect.py horiz(): a square counts as horizontal


def room_type_from_name(name: str) -> str | None:
    """PlanTo3D's room type for a room label, by detect.py's keyword rule.

    Unlike detect.py the parts of a dotted word are looked at too, so "ENT.LOBBY" is a
    passage and "M.BED" a bedroom.
    """
    tokens: list[str] = []
    for raw in re.split(r"[\s/]+", name):
        whole = raw.strip(".,:()").upper()
        tokens.append(whole)
        tokens += [part for part in whole.split(".") if part]
    for room_type, keys in ROOM_TYPES:
        for key in keys:
            k = key.strip(".")
            if any(t == k or (len(key) >= 3 and t.startswith(k)) for t in tokens):
                return room_type
    return None


def room_type(room: Mapping[str, Any]) -> str:
    """The most specific thing the plan says about a room, most reliable source first."""
    tag = room.get("tag")
    if isinstance(tag, str) and tag in GENERATOR_TAGS:
        return GENERATOR_TAGS[tag]  # the generator knows what it drew
    explicit = room.get("type")
    if isinstance(explicit, str) and explicit in PLANTO3D_TYPES:
        return explicit  # the 3D adapter's own key on a PlanJSON
    named = room_type_from_name(_text(room.get("name")))
    if named:
        return named
    boq = room.get("boq_type")
    if isinstance(boq, str) and boq in BOQ_TYPES:
        return BOQ_TYPES[boq]
    kind = room.get("boq_kind") if room.get("kind") is None else room.get("kind")
    return ROOM_KINDS.get(kind, "room") if isinstance(kind, str) else "room"


# ---------------------------------------------------------------- the conversion
def planjson_to_planto3d(
    plan: Mapping[str, Any],
    *,
    source_name: str = "",
    reader: str = "ai",
    offset_from: Literal["centre", "start"] | None = None,
    y_down: bool = True,
    diagonal: Literal["steps", "skip"] = "steps",
    registration: Mapping[str, Any] | None = None,
) -> ConvertResult:
    """Convert a PlanJSON dict (`PlanJSON.model_dump()`, or `plans.plan_json`) for PlanTo3D.

    `reader` says who read the drawing and is written to the plan: "ai" for the PDF parser,
    "generator" for our floor plan generator.

    `offset_from` is what an opening's `offset` measures from the start of its wall. The two
    producers disagree: the parser measures to the opening's centre (and also writes that
    point as `position`), the generator to its near edge. Left as None it follows `reader`.
    An opening's `position`, when present, always wins.

    `y_down` is True for both producers (y grows down the page).

    `registration` is the hook for laying the plan over its PDF page in the review page;
    this function does not know the page. It is {"plan": {...}, "floors": [{...}, ...]}:
    the first dict is merged into the plan, the n-th of the list into the n-th floor
    (`page`, `origin_pt`, `scale_pt_per_ft`, or whatever the review page comes to need).
    Without it every floor says page 1 with its origin at the page's top-left corner, so
    the page image is not lined up with the plan.
    """
    try:
        result = _convert(
            plan,
            source_name=source_name,
            reader=reader,
            offset_from=offset_from or ("start" if reader == "generator" else "centre"),
            y_down=y_down,
            diagonal=diagonal,
            registration=registration,
        )
    # A stored or model-written document can be wrong in ways no schema rules out. The
    # caller's fallback (trace the plan by hand) is better than a failed upload.
    except (ArithmeticError, LookupError, TypeError, ValueError) as error:
        return ConvertResult(None, reason=f"The plan could not be converted ({error!r}).")
    if result.plan is None:
        return result
    return ConvertResult(result.plan, result.notes, check_plausible(result.plan))


def _convert(
    plan: Mapping[str, Any],
    *,
    source_name: str,
    reader: str,
    offset_from: str,
    y_down: bool,
    diagonal: str,
    registration: Mapping[str, Any] | None,
) -> ConvertResult:
    if not isinstance(plan, Mapping):
        return ConvertResult(None, reason="The plan is not a PlanJSON document.")
    units = plan.get("units", "m")
    to_ft = _TO_FT.get(units) if isinstance(units, str) else None
    if to_ft is None:
        return ConvertResult(None, reason=f"The plan is in an unknown unit ({units!r}).")
    levels = _dicts(plan.get("levels"))
    if not levels:
        return ConvertResult(None, reason="The plan has no levels.")

    notes: list[str] = []
    floors: list[dict[str, Any]] = []
    for position, level in enumerate(levels):
        name = _floor_name(level, len(floors))
        floor = _floor(
            level,
            name,
            to_ft=to_ft,
            offset_from=offset_from,
            y_down=y_down,
            diagonal=diagonal,
            notes=notes,
        )
        if floor is None:
            notes.append(f"{name}: left out, it has no usable walls (level {position}).")
            continue
        floor["level"] = len(floors)
        floors.append(floor)
    if not floors:
        return ConvertResult(None, notes, reason="The plan has no walls.")

    if len(floors) > 1:
        notes.append(
            "Each floor is placed by the lower-left corner of its own walls, and there are no "
            "stair flights (PlanJSON has none): check that the floors sit over each other."
        )
    scale_source = "labels" if plan.get("scale_source") in _REAL_SCALES else "assumed"
    if scale_source == "assumed":
        notes.append("The scale of the drawing was assumed: check a known size in review.")
    thicknesses = sorted(min(w[1] - w[0], w[3] - w[2]) for f in floors for w in f["walls"])
    out: dict[str, Any] = {
        "version": 1,
        "source": source_name,
        "reader": reader,
        "units": "ft",
        "scale_pt_per_ft": UNREGISTERED_PT_PER_FT,
        # the review page only asks whether this is "labels"; anything else reads "GUESSED"
        "scale_source": scale_source,
        "wall_pt": round(thicknesses[len(thicknesses) // 2] * UNREGISTERED_PT_PER_FT, 2),
        "floor_height": _floor_height(levels, to_ft, notes),
        "slab": SLAB_FT,
        "floors": floors,
    }
    if isinstance(registration, Mapping):
        if isinstance(registration.get("plan"), Mapping):
            out.update(registration["plan"])
        for floor, extra in zip(floors, registration.get("floors") or [], strict=False):
            if isinstance(extra, Mapping):
                floor.update(extra)
    return ConvertResult(out, notes)


def _floor_name(level: Mapping[str, Any], index: int) -> str:
    """detect.py's rule: the title in title case without " Plan"; a bare "Floor Plan" is no name."""
    name = _text(level.get("name")).title().replace(" Plan", "").strip()
    if name and name.lower() != "floor":
        return name[:60]
    return _FLOOR_NAMES[index] if index < len(_FLOOR_NAMES) else f"Floor {index}"


def _floor_height(levels: list[dict[str, Any]], to_ft: float, notes: list[str]) -> float:
    """PlanTo3D has one storey height. Ours is used only when the drawing states it."""
    stated = [
        h * to_ft
        for lv in levels
        if lv.get("wall_height_source") == "stated" and (h := _num(lv.get("wall_height")))
    ]
    if not stated:
        return DEFAULT_FLOOR_HEIGHT_FT
    height = min(MAX_FLOOR_HEIGHT_FT, max(MIN_FLOOR_HEIGHT_FT, max(stated)))
    if len({round(h, 1) for h in stated}) > 1 or abs(height - max(stated)) > 0.05:
        notes.append(f"Every storey is built {height:.1f} ft high (PlanTo3D has one height).")
    return round(height, 2)


def _floor(
    level: Mapping[str, Any],
    name: str,
    *,
    to_ft: float,
    offset_from: str,
    y_down: bool,
    diagonal: str,
    notes: list[str],
) -> dict[str, Any] | None:
    flip = -1.0 if y_down else 1.0

    def point(raw: Any) -> tuple[float, float] | None:
        if not isinstance(raw, list | tuple) or len(raw) < 2:
            return None
        x, y = _num(raw[0]), _num(raw[1])
        return None if x is None or y is None else (x * to_ft, y * to_ft * flip)

    def say(message: str) -> None:
        notes.append(f"{name}: {message}")

    # ---- walls: centre lines -> axis walls, slanted pieces, column blocks
    walls: dict[str, _Wall] = {}
    ordered: list[_Wall] = []
    blocks: list[Rect] = []  # steps of slanted walls and columns: rectangles without openings
    columns = 0
    slanted: set[str] = set()
    clamped = 0
    for index, raw in enumerate(_dicts(level.get("walls"))):
        wall_id = str(raw.get("id") or f"wall {index + 1}")
        a, b = point(raw.get("start")), point(raw.get("end"))
        if a is None or b is None:
            say(f"wall {wall_id} has no end points and was left out.")
            continue
        exterior = raw.get("kind") == "exterior" or raw.get("is_exterior") is True
        t = (_num(raw.get("thickness")) or 0.0) * to_ft
        if t <= 0:
            t = EXTERIOR_WALL_FT if exterior else INTERIOR_WALL_FT
        elif not MIN_WALL_FT <= t <= MAX_WALL_FT:
            t, clamped = min(MAX_WALL_FT, max(MIN_WALL_FT, t)), clamped + 1
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < MIN_WALL_LENGTH_FT:
            say(f"wall {wall_id} is under {MIN_WALL_LENGTH_FT * 12:.0f} in long and was left out.")
            continue
        off = min(abs(dx), abs(dy))
        if off > STRAIGHT_FT and math.degrees(math.asin(off / length)) > STRAIGHTEN_DEG:
            slanted.add(wall_id)
            if diagonal == "skip":
                say(f"wall {wall_id} is slanted ({length:.1f} ft) and was left out.")
                continue
            steps = max(1, math.ceil(length / STEP_FT))
            for i in range(steps):
                p = (a[0] + dx * i / steps, a[1] + dy * i / steps)
                q = (a[0] + dx * (i + 1) / steps, a[1] + dy * (i + 1) / steps)
                blocks.append(
                    [
                        min(p[0], q[0]) - t / 2,
                        max(p[0], q[0]) + t / 2,
                        min(p[1], q[1]) - t / 2,
                        max(p[1], q[1]) + t / 2,
                    ]
                )
            say(f"wall {wall_id} is slanted ({length:.1f} ft) and is drawn as {steps} short steps.")
            continue
        if off > STRAIGHT_FT:
            say(f"wall {wall_id} was straightened (it was {off * 12:.0f} in off its axis).")
        if abs(dx) >= abs(dy):
            wall = _Wall(wall_id, True, (a[1] + b[1]) / 2, 0, 0, t, start=a[0], end=b[0])
        else:
            wall = _Wall(wall_id, False, (a[0] + b[0]) / 2, 0, 0, t, start=a[1], end=b[1])
        wall.drawn = abs(wall.end - wall.start)
        walls.setdefault(wall_id, wall)
        ordered.append(wall)
    if clamped:
        say(
            f"{clamped} wall(s) had a thickness outside {MIN_WALL_FT * 12:.0f}-"
            f"{MAX_WALL_FT * 12:.0f} in; it was brought inside that range."
        )
    if not ordered and not blocks:
        return None

    # An opening whose middle lies past the end of its wall says the wall is longer than
    # its centre line (a reader that cut a wall short keeps the openings' offsets). The wall
    # is run on to hold them, and on to a crossing wall when one is near: walls end at walls.
    for raw in _dicts(level.get("openings")):
        host = walls.get(str(raw.get("wall_id")))
        offset, width = _num(raw.get("offset")), (_num(raw.get("width")) or 0.0) * to_ft
        if host is None or offset is None or width <= 0:
            continue
        middle = offset * to_ft + (width / 2 if offset_from == "start" else 0.0)
        if middle > host.drawn + 0.05:
            host.reach = max(host.reach, middle + width / 2)
    for w in ordered:
        if w.reach > w.drawn:
            way = 1.0 if w.end >= w.start else -1.0
            end = w.start + way * w.reach
            crossing = [
                q.c
                for q in ordered
                if q.horizontal != w.horizontal
                and q.a_low() - JOIN_FT <= w.c <= q.a_high() + JOIN_FT
                and 0 <= (q.c - end) * way <= EXTEND_FT
            ]
            end = min(crossing, key=lambda c: abs(c - end)) if crossing else end
            say(
                f"wall {w.wall_id} is drawn {w.drawn:.1f} ft long but has openings past its "
                f"end: it was lengthened to {abs(end - w.start):.1f} ft."
            )
            w.end = end
        w.a0 = w.lo = w.inner0 = w.a_low()
        w.a1 = w.hi = w.inner1 = w.a_high()

    # A centre line stops on the centre line of the wall it meets, which leaves a notch at
    # every corner. Each end is run on to the far face of the wall it meets, so the
    # rectangles overlap at corners and T junctions as PlanTo3D's own do.
    for w in ordered:
        for q in ordered:
            if q.horizontal == w.horizontal or not q.a0 - JOIN_FT <= w.c <= q.a1 + JOIN_FT:
                continue
            if abs(q.c - w.a0) <= JOIN_FT + q.t / 2:
                w.lo = min(w.lo, q.c - q.t / 2)
                w.inner0 = max(w.inner0, q.c + q.t / 2)
            if abs(q.c - w.a1) <= JOIN_FT + q.t / 2:
                w.hi = max(w.hi, q.c + q.t / 2)
                w.inner1 = min(w.inner1, q.c - q.t / 2)

    for raw in _dicts(level.get("columns")):
        centre = point(raw.get("position"))
        width = (_num(raw.get("width")) or 0.0) * to_ft
        depth = (_num(raw.get("depth")) or 0.0) * to_ft
        if centre is None or min(width, depth) < MIN_RECT_FT or max(width, depth) > 6.0:
            continue
        box = [
            centre[0] - width / 2,
            centre[0] + width / 2,
            centre[1] - depth / 2,
            centre[1] + depth / 2,
        ]
        rects_so_far = [w.rect() for w in ordered]
        corners = ((box[0], box[2]), (box[0], box[3]), (box[1], box[2]), (box[1], box[3]))
        if not all(any(_contains(r, x, y) for r in rects_so_far) for x, y in corners):
            blocks.append(box)  # a column buried in a wall adds nothing
            columns += 1

    # ---- origin: the lower-left corner of everything that is a wall
    wall_rects = [w.rect() for w in ordered] + blocks
    x_origin = min(r[0] for r in wall_rects)
    y_origin = min(r[2] for r in wall_rects)

    def moved(r: Sequence[float]) -> Rect:
        return [
            round(r[0] - x_origin, 3) + 0.0,
            round(r[1] - x_origin, 3) + 0.0,
            round(r[2] - y_origin, 3) + 0.0,
            round(r[3] - y_origin, 3) + 0.0,
        ]

    out_walls = [moved(r) for r in wall_rects]
    size = [
        round(max(r[1] for r in out_walls), 2),
        round(max(r[3] for r in out_walls), 2),
    ]

    # ---- openings: a rectangle across the wall, where the wall says the opening is
    openings: list[dict[str, Any]] = []
    for index, raw in enumerate(_dicts(level.get("openings"))):
        opening_id = str(raw.get("id") or f"opening {index + 1}")
        kind = raw.get("type") if raw.get("type") in ("door", "window", "opening") else "opening"
        host_id = str(raw.get("wall_id"))
        host = walls.get(host_id)
        if host is None:
            why = "is slanted" if host_id in slanted else "is not in the plan"
            say(f"{kind} {opening_id} was left out: its wall ({host_id}) {why}.")
            continue
        width = (_num(raw.get("width")) or 0.0) * to_ft
        centre = _opening_centre(raw, host, point, to_ft, offset_from, width)
        if centre is None or width <= 0:
            say(f"{kind} {opening_id} was left out: it has no position or no width.")
            continue
        room_for_it = host.inner1 - host.inner0
        if room_for_it < MIN_OPENING_FT:
            say(f"{kind} {opening_id} was left out: its wall is too short for an opening.")
            continue
        fitted = min(width, room_for_it)
        s0 = min(max(centre - fitted / 2, host.inner0), host.inner1 - fitted)
        s1 = s0 + fitted
        if fitted < width - 0.05:
            say(
                f"{kind} {opening_id} is {width:.1f} ft wide but its wall has room for "
                f"{room_for_it:.1f} ft: it was narrowed."
            )
        elif abs((s0 + s1) / 2 - centre) > MOVED_FT:
            say(f"{kind} {opening_id} ran past the end of its wall and was moved onto it.")
        if any(s0 < b - 0.05 and a < s1 - 0.05 for a, b in host.taken):
            say(f"{kind} {opening_id} was left out: it overlaps another opening on its wall.")
            continue
        host.taken.append((s0, s1))
        half = host.t / 2
        rect = (
            [s0, s1, host.c - half, host.c + half]
            if host.horizontal
            else [
                host.c - half,
                host.c + half,
                s0,
                s1,
            ]
        )
        axis = "x" if host.horizontal else "y"
        openings.append({"type": kind, "rect": moved(rect), "axis": axis})

    # ---- rooms: polygon -> rectangles between the wall faces
    rooms: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    for index, raw in enumerate(_dicts(level.get("rooms"))):
        label = _text(raw.get("name"))[:80]
        shown = label or str(raw.get("id") or f"room {index + 1}")
        polygon = [p for p in map(point, raw.get("polygon") or []) if p is not None]
        polygon = [(x - x_origin, y - y_origin) for x, y in polygon]
        if len(polygon) < 3:
            say(f"room {shown} has no outline and was left out.")
            continue
        rects, approximated = _polygon_rects(polygon, out_walls)
        area = round(sum(_area(r) for r in rects), 1)
        if not rects or area < MIN_ROOM_SQFT:
            say(f"room {shown} is smaller than {MIN_ROOM_SQFT:.0f} sq ft and was left out.")
            continue
        if approximated:
            say(f"room {shown} has slanted edges: its floor is made of {len(rects)} rectangles.")
        rooms.append(
            {
                "region": len(rooms) + 2,  # detect.py numbers its flood-fill regions from 2
                "type": room_type(raw),
                "area": area,
                "label": label,
                "dims": None,
                "rects": rects,
            }
        )
        biggest = max(rects, key=_area)
        if label:
            at = [round((biggest[0] + biggest[1]) / 2, 3), round((biggest[2] + biggest[3]) / 2, 3)]
            labels.append({"text": label, "at": at})

    lows = _low_walls(out_walls, rooms)
    if columns:
        lows[-columns:] = [0] * columns  # a column carries the floor above: never a parapet
    if any(lows):
        say(f"{sum(lows)} wall(s) beside outdoor areas only are built low (parapet height).")
    title = _text(level.get("name")).upper()[:80]
    return {
        "title": title or None,
        "origin_pt": [0.0, 0.0],
        "size": size,
        "walls": [[*r, low] for r, low in zip(out_walls, lows, strict=True)],
        "openings": openings,
        "rooms": rooms,
        "stairs": [],
        "labels": labels,
        "page": 1,
        "name": name,
    }


def _opening_centre(
    raw: Mapping[str, Any], host: _Wall, point: Any, to_ft: float, offset_from: str, width: float
) -> float | None:
    """Where the opening's middle is along its wall (the wall's own running coordinate)."""
    offset = _num(raw.get("offset"))
    lead = width / 2 if offset_from == "start" else 0.0
    along = None if offset is None else offset * to_ft + lead
    at = point(raw.get("position"))
    # A position is where the reader saw the opening, so it wins - unless the offset runs
    # past the wall as drawn: the parser then pinned the position to the wall's end.
    if at is not None and (along is None or along <= host.drawn + 0.05):
        return at[0] if host.horizontal else at[1]
    if along is None:
        return None
    return host.start + along if host.end >= host.start else host.start - along


def _inside_polygon(polygon: Sequence[tuple[float, float]], x: float, y: float) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(polygon, [*polygon[1:], polygon[0]], strict=True):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def _distinct(values: list[float], gap: float = 0.02) -> list[float]:
    out: list[float] = []
    for v in sorted(values):
        if not out or v - out[-1] > gap:
            out.append(v)
    return out


def _polygon_rects(
    polygon: Sequence[tuple[float, float]], walls: Sequence[Sequence[float]]
) -> tuple[list[Rect], bool]:
    """A room outline as a few rectangles, with the walls cut out of it.

    Our rooms are measured on wall centre lines or on wall faces, depending on who read the
    drawing; PlanTo3D's furniture rules need the clear floor between the wall faces. So the
    outline is cut on a grid of its own corners and the wall faces it touches, and the cells
    inside the outline and outside every wall are merged back (rows first, as detect.py does).
    Returns the rectangles and whether the outline had slanted edges (it is then approximated).
    """
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    box = (min(xs), max(xs), min(ys), max(ys))
    edges = zip(polygon, [*polygon[1:], polygon[0]], strict=True)
    slanted = any(min(abs(a[0] - b[0]), abs(a[1] - b[1])) > STRAIGHT_FT for a, b in edges)
    near = [w for w in walls if w[0] < box[1] and box[0] < w[1] and w[2] < box[3] and box[2] < w[3]]
    for w in near:
        xs += [min(max(v, box[0]), box[1]) for v in w[:2]]
        ys += [min(max(v, box[2]), box[3]) for v in w[2:4]]
    if slanted:
        cell = max(SLANT_CELL_FT, (box[1] - box[0]) / 120, (box[3] - box[2]) / 120)
        xs += [box[0] + i * cell for i in range(1, int((box[1] - box[0]) / cell) + 1)]
        ys += [box[2] + i * cell for i in range(1, int((box[3] - box[2]) / cell) + 1)]
    gx, gy = _distinct(xs), _distinct(ys)

    def free(i: int, j: int) -> bool:
        x, y = (gx[i] + gx[i + 1]) / 2, (gy[j] + gy[j + 1]) / 2
        return _inside_polygon(polygon, x, y) and not any(_contains(w, x, y) for w in near)

    rects: list[Rect] = []
    growing: dict[tuple[int, int], int] = {}  # run of cells (i0, i1) -> the row it started on
    for j in range(len(gy)):
        runs: list[tuple[int, int]] = []
        start: int | None = None
        for i in range(len(gx)):
            filled = j < len(gy) - 1 and i < len(gx) - 1 and free(i, j)
            if filled and start is None:
                start = i
            elif not filled and start is not None:
                runs.append((start, i - 1))
                start = None
        for run, j0 in list(growing.items()):
            if run not in runs:
                rects.append([gx[run[0]], gx[run[1] + 1], gy[j0], gy[j]])
                del growing[run]
        for run in runs:
            growing.setdefault(run, j)
    rects = [
        [round(v, 3) + 0.0 for v in r]
        for r in rects
        if min(r[1] - r[0], r[3] - r[2]) >= MIN_RECT_FT
    ]
    return rects, slanted


def _low_walls(walls: Sequence[Sequence[float]], rooms: Sequence[Mapping[str, Any]]) -> list[int]:
    """1 for a wall with outdoor rooms, or nothing, on both sides: a boundary or parapet wall.

    detect.py's rule, with one difference. Its rooms cover the whole floor; ours cover what
    the plan names. A wall with no room at all beside it is therefore kept full height: it
    is more likely a wall of a room nobody outlined than a parapet.
    """

    def type_at(x: float, y: float) -> str | None:
        for room in rooms:
            if any(_contains(r, x, y) for r in room["rects"]):
                return room["type"]
        return None

    lows: list[int] = []
    for w in walls:
        sides: list[str | None] = []
        for share in (0.1, 0.3, 0.5, 0.7, 0.9):
            if _is_horizontal(w):
                x = w[0] + share * (w[1] - w[0])
                sides += [type_at(x, w[2] - PROBE_FT), type_at(x, w[3] + PROBE_FT)]
            else:
                y = w[2] + share * (w[3] - w[2])
                sides += [type_at(w[0] - PROBE_FT, y), type_at(w[1] + PROBE_FT, y)]
        seen = [s for s in sides if s is not None]
        low = bool(seen) and all(s in OUTDOOR and s != "open" for s in seen)
        lows.append(1 if low else 0)
    return lows


# ---------------------------------------------------------------- plausibility
def check_plausible(plan: Mapping[str, Any]) -> list[str]:
    """Why a PlanTo3D plan looks wrong; an empty list when it looks like a house.

    Works on any PlanTo3D plan JSON, converted here or written by its detector. The checks
    and their thresholds (constants at the top of this file):

    - at least MIN_WALLS walls on every floor;
    - each floor between MIN_SIDE_FT and MAX_SIDE_FT on both sides;
    - the median wall thickness between MIN_MEDIAN_WALL_FT and MAX_MEDIAN_WALL_FT
      (anything else means the scale is wrong);
    - at least one indoor room, and at least one door;
    - no indoor room larger than MAX_ROOM_SQFT, and the indoor rooms together no larger
      than MAX_OVERLAP times the walls' bounding box (they overlap otherwise);
    - all rooms together cover at least MIN_COVER of the bounding box;
    - no indoor room with more than MAX_OUTSIDE of its area outside the bounding box;
    - a closed outline: with the walls and openings as barriers, at most MAX_LEAK of the
      indoor floor area can be reached from outside the house.
    """
    floors = _dicts(plan.get("floors")) if isinstance(plan, Mapping) else []
    if not floors:
        return ["The plan has no floors."]
    problems: list[str] = []
    for index, floor in enumerate(floors):
        name = _text(floor.get("name")) or f"Floor {index}"
        for problem in _floor_problems(floor):
            problems.append(f"{name}: {problem}")
    return problems


def _floor_problems(floor: Mapping[str, Any]) -> list[str]:
    walls = [w for w in floor.get("walls") or [] if isinstance(w, list | tuple) and len(w) >= 4]
    if len(walls) < MIN_WALLS:
        return [f"only {len(walls)} wall(s); a house needs at least {MIN_WALLS}."]
    problems: list[str] = []
    box = (
        min(w[0] for w in walls),
        max(w[1] for w in walls),
        min(w[2] for w in walls),
        max(w[3] for w in walls),
    )
    width, depth = box[1] - box[0], box[3] - box[2]
    if not (MIN_SIDE_FT <= width <= MAX_SIDE_FT and MIN_SIDE_FT <= depth <= MAX_SIDE_FT):
        problems.append(
            f"it measures {width:.0f} x {depth:.0f} ft; expected between "
            f"{MIN_SIDE_FT:.0f} and {MAX_SIDE_FT:.0f} ft each way."
        )
    thickness = sorted(min(w[1] - w[0], w[3] - w[2]) for w in walls)[len(walls) // 2]
    if not MIN_MEDIAN_WALL_FT <= thickness <= MAX_MEDIAN_WALL_FT:
        problems.append(f"its walls are {thickness * 12:.0f} in thick; the scale looks wrong.")

    openings = [o for o in _dicts(floor.get("openings")) if len(o.get("rect") or []) >= 4]
    if not any(o.get("type") in ("door", "opening") for o in openings):
        problems.append("it has no door.")
    rooms = [r for r in _dicts(floor.get("rooms")) if r.get("rects")]
    indoor = [r for r in rooms if r.get("type") in INDOOR]
    if not indoor:
        problems.append("it has no indoor room.")
    box_area = max(width * depth, 1e-6)
    indoor_area = sum(_area(q) for r in indoor for q in r["rects"])
    for room in indoor:
        area = sum(_area(q) for q in room["rects"])
        label = _text(room.get("label")) or str(room.get("type"))
        if area > MAX_ROOM_SQFT:
            problems.append(f"room {label} is {area:.0f} sq ft.")
        within = sum(
            _area([max(q[0], box[0]), min(q[1], box[1]), max(q[2], box[2]), min(q[3], box[3])])
            for q in room["rects"]
        )
        if area > 0 and 1 - within / area > MAX_OUTSIDE:
            problems.append(f"room {label} lies outside the walls.")
    if indoor_area > MAX_OVERLAP * box_area:
        problems.append("its rooms overlap each other.")
    if rooms and sum(_area(q) for r in rooms for q in r["rects"]) < MIN_COVER * box_area:
        problems.append("its rooms cover very little of the area inside the walls.")
    if indoor and width <= 4 * MAX_SIDE_FT and depth <= 4 * MAX_SIDE_FT:
        leak = _leak(walls, openings, indoor, box)
        if leak > MAX_LEAK:
            problems.append(
                f"its outline is not closed: {leak:.0%} of the indoor floor can be reached "
                "from outside without passing a door or a window."
            )
    return problems


def _leak(
    walls: Sequence[Sequence[float]],
    openings: Sequence[Mapping[str, Any]],
    indoor: Sequence[Mapping[str, Any]],
    box: tuple[float, float, float, float],
) -> float:
    """Share of the indoor floor a flood from outside reaches (walls and openings stop it).

    The grid cell is 0.5 ft, or coarser on a very large plan (at most 160 cells a side). A
    cell touched by a wall is closed, so gaps narrower than a cell do not count as leaks.
    """
    cell = max(0.5, (box[1] - box[0]) / 160, (box[3] - box[2]) / 160)
    x0, y0 = box[0] - 2 * cell, box[2] - 2 * cell
    nx = int((box[1] - box[0]) / cell) + 5
    ny = int((box[3] - box[2]) / cell) + 5
    closed = [[False] * nx for _ in range(ny)]
    for r in [*walls, *(o["rect"] for o in openings)]:
        i0, i1 = int((r[0] - x0) / cell), int(math.ceil((r[1] - x0) / cell))
        j0, j1 = int((r[2] - y0) / cell), int(math.ceil((r[3] - y0) / cell))
        for j in range(max(j0, 0), min(j1, ny)):
            for i in range(max(i0, 0), min(i1, nx)):
                closed[j][i] = True
    reached = [[False] * nx for _ in range(ny)]
    reached[0][0] = True
    stack = [(0, 0)]
    while stack:
        i, j = stack.pop()
        for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= a < nx and 0 <= b < ny and not closed[b][a] and not reached[b][a]:
                reached[b][a] = True
                stack.append((a, b))
    total = leaked = 0
    for room in indoor:
        for r in room["rects"]:
            i0, i1 = max(int((r[0] - x0) / cell), 0), min(int((r[1] - x0) / cell) + 1, nx)
            j0, j1 = max(int((r[2] - y0) / cell), 0), min(int((r[3] - y0) / cell) + 1, ny)
            for j in range(j0, j1):
                y = y0 + (j + 0.5) * cell
                for i in range(i0, i1):
                    x = x0 + (i + 0.5) * cell
                    if closed[j][i] or not _contains(r, x, y):
                        continue
                    total += 1
                    leaked += reached[j][i]
    return leaked / total if total else 0.0
