"""Engineering checks on the building model, run on every version.

Values are in CHECKS (defaults from the Dubai Building Code 2021 Part K; see
docs/pro/2d/RULES.md, every value "to be confirmed against the Dubai Building Code by an
engineer"). Each issue is critical, warning or info; a plan with a critical issue is never
delivered without saying so (the chat reply and the notes panel list them).
"""

import math
from dataclasses import dataclass, field
from typing import Literal

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from app.modules.ai.floorplan.model.building import Building, Storey

Severity = Literal["critical", "warning", "info"]


@dataclass
class Issue:
    code: str
    severity: Severity
    message: str
    rooms: list[str] = field(default_factory=list)
    ref: str = ""

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "rooms": self.rooms,
            "ref": self.ref,
        }


HABITABLE = {
    "bedroom",
    "master_bedroom",
    "living",
    "family_hall",
    "majlis",
    "dining",
    "study",
    "gym",
    "bar",
}
SERVICE_ROOMS = {"maid_room", "driver_room"}
WET = {"bath", "toilet", "kitchen", "utility"}
NON_HABITABLE_DOOR = {"bath", "toilet", "store", "dress", "utility", "shaft"}

CHECKS = {
    # (net area m2, least net dimension mm), DBC K.5.3.1 Table K.2 (bath / WC: practice)
    "min_room": {
        "habitable": (10.5, 3000),
        "service_room": (5.5, 2100),
        "kitchen": (5.4, 1800),
        "bath": (2.5, 1200),
        "toilet": (1.1, 850),
        "lobby": (0.0, 1000),
        "passage": (0.0, 1000),
    },
    "door_clear_mm": {"main": 915, "room": 915, "wet": 710},  # DBC K.5.4.1 Table K.4
    "corridor_mm": 1000,  # DBC K.5.5.1
    "glazing_share": {"habitable": 0.10, "kitchen": 0.10, "service_room": 0.08},  # K.5.4.2.1
    "stair": {  # DBC K.5.5.2
        "riser": (100, 180),
        "tread_min": 280,
        "width_min": 1000,
        "headroom_min": 2300,
        "landing_min": 1000,
    },
    "work_triangle_mm": {"leg": (1200, 2700), "sum": (4000, 7900)},  # NKBA guideline
    "wc_side_mm": 400,  # DBC K.5.7.2
    "wet_stack_overlap": 0.5,
    "coverage": (0.65, 0.75),
    "dbc_setback_m": 3.0,  # DBC K.5.2.4 Table K.1, standalone villa
}


def _net(room, st: Storey) -> Polygon:
    p = Polygon(room.polygon)
    bands = []
    for w in st.walls:
        if room.id not in w.rooms:
            continue
        h = w.thickness / 2
        x0, x1 = sorted((w.a[0], w.b[0]))
        y0, y1 = sorted((w.a[1], w.b[1]))
        bands.append(box(x0 - h, y0 - h, x1 + h, y1 + h))
    return p.difference(unary_union(bands)) if bands else p


def _least(poly: Polygon) -> float:
    x0, y0, x1, y1 = poly.bounds
    return min(x1 - x0, y1 - y0)


def run_checks(b: Building) -> list[Issue]:
    out: list[Issue] = []
    c = CHECKS
    for st in b.storeys:
        names = {r.id: r.name for r in st.rooms}
        doors_of: dict[str, list] = {r.id: [] for r in st.rooms}
        for o in st.openings:
            for rid in o.rooms:
                if rid in doors_of and o.kind == "door":
                    doors_of[rid].append(o)
        for r in st.rooms:
            if r.type == "shaft":
                continue
            net = _net(r, st)
            area, least = net.area / 1e6, _least(net)
            group = (
                "habitable"
                if r.type in HABITABLE
                else "service_room"
                if r.type in SERVICE_ROOMS
                else r.type
            )
            rule = c["min_room"].get(group)
            if rule:
                min_a, min_d = rule
                if area < min_a - 0.05 or least < min_d - 25:
                    out.append(
                        Issue(
                            "ROOM_SIZE",
                            "critical",
                            f"{r.name} is {area:.1f} m², {least / 1000:.2f} m at its narrowest; "
                            f"the minimum is {min_a:g} m² and {min_d / 1000:.2f} m",
                            [r.id],
                            "DBC K.5.3.1 Table K.2",
                        )
                    )
            # every room can be entered
            if not doors_of[r.id]:
                out.append(Issue("NO_DOOR", "critical", f"{r.name} has no door", [r.id]))
            # daylight and ventilation
            windows = [o for o in st.openings if o.kind == "window" and o.rooms[0] == r.id]
            # a sliding glass door to the outside is glazing too
            glazed_doors = [
                o
                for o in st.openings
                if o.kind == "door"
                and o.operation == "sliding"
                and r.id in o.rooms
                and any(x is None or x not in names for x in o.rooms)
            ]
            share = c["glazing_share"].get(group if group != r.type else r.type)
            if share is not None:
                glass = sum(o.width * o.height for o in windows + glazed_doors) / 1e6
                if not windows and not glazed_doors:
                    out.append(
                        Issue(
                            "NO_WINDOW",
                            "critical",
                            f"{r.name} has no window on an outside wall",
                            [r.id],
                            "DBC K.5.4.2",
                        )
                    )
                elif glass < share * area:
                    out.append(
                        Issue(
                            "GLAZING",
                            "warning",
                            f"{r.name} has {glass:.2f} m² of window, {share:.0%} of its floor "
                            f"needs {share * area:.2f} m²",
                            [r.id],
                            "DBC K.5.4.2.1",
                        )
                    )
            if r.type in ("bath", "toilet") and not windows:
                out.append(
                    Issue(
                        "VENTILATION",
                        "warning",
                        f"{r.name} has no window: it needs a mechanical extract fan to outside",
                        [r.id],
                        "DBC K.5.7.1, K.10.1.6",
                    )
                )
            if r.type in ("lobby", "passage") and least < c["corridor_mm"] - 25:
                out.append(
                    Issue(
                        "CORRIDOR",
                        "critical",
                        f"{r.name} is {least / 1000:.2f} m wide; corridors need "
                        f"{c['corridor_mm'] / 1000:.1f} m",
                        [r.id],
                        "DBC K.5.5.1",
                    )
                )
        out += _doors(st)
        out += _stairs(st, names)
        out += _kitchens(st, names)
        out += _wcs(st, names)
    out += _wet_stack(b)
    out += _site(b)
    return out


def _doors(st: Storey) -> list[Issue]:
    """Each door once, against the minimum for the space it serves: the main entrance,
    a room, or a bathroom / WC / store / dressing room (DBC K.5.4.1 Table K.4)."""
    widths = CHECKS["door_clear_mm"]
    types = {r.id: r.type for r in st.rooms}
    names = {r.id: r.name for r in st.rooms}
    out = []
    for o in st.openings:
        if o.kind != "door":
            continue
        sides = [rid for rid in o.rooms if rid in types]
        if o.main_entrance:
            need = widths["main"]
        elif any(types[rid] in NON_HABITABLE_DOOR for rid in sides):
            need = widths["wet"]
        else:
            need = widths["room"]
        if o.width < need:
            where = " / ".join(names[rid] for rid in sides) or "outside"
            out.append(
                Issue(
                    "DOOR_WIDTH",
                    "critical",
                    f"door {o.id} ({where}) is {o.width} mm; at least {need} mm clear",
                    sides,
                    "DBC K.5.4.1 Table K.4",
                )
            )
    return out


def _stairs(st: Storey, names: dict[str, str]) -> list[Issue]:
    s_ = CHECKS["stair"]
    out = []
    for s in st.stairs:
        bad = []
        if not s_["riser"][0] <= s.riser <= s_["riser"][1]:
            bad.append(f"riser {s.riser} mm (100-180)")
        if s.tread < s_["tread_min"]:
            bad.append(f"tread {s.tread} mm (at least 280)")
        if s.width < s_["width_min"]:
            bad.append(f"width {s.width} mm (at least 1000)")
        if s.headroom < s_["headroom_min"]:
            bad.append(f"headroom {s.headroom} mm (at least 2300)")
        if s.landing and min(s.landing[2], s.landing[3]) < s_["landing_min"]:
            bad.append(f"landing {min(s.landing[2], s.landing[3])} mm (at least 1000)")
        need = (s.risers - (1 if s.landing is None else 2)) * s.tread
        run = sum(f.w if f.axis == "x" else f.h for f in s.flights)
        if run + 50 < need:
            bad.append("the room is too short for the flights")
        if bad:
            out.append(
                Issue(
                    "STAIR",
                    "critical",
                    f"{names.get(s.room, 'stair')}: " + "; ".join(bad),
                    [s.room],
                    "DBC K.5.5.2",
                )
            )
    return out


def _kitchens(st: Storey, names: dict[str, str]) -> list[Issue]:
    leg_lo, leg_hi = CHECKS["work_triangle_mm"]["leg"]
    sum_lo, sum_hi = CHECKS["work_triangle_mm"]["sum"]
    out = []
    for r in st.rooms:
        if r.type != "kitchen":
            continue
        pts = {
            f.kind: (f.x, f.y)
            for f in st.fixtures
            if f.room == r.id and f.kind in ("sink", "hob", "fridge")
        }
        if len(pts) < 3:
            out.append(
                Issue(
                    "WORK_TRIANGLE",
                    "warning",
                    f"{r.name}: sink, hob and fridge are not all placed; check the triangle",
                    [r.id],
                    "NKBA kitchen guideline",
                )
            )
            continue
        legs = [
            math.dist(pts[a], pts[b])
            for a, b in (("sink", "hob"), ("hob", "fridge"), ("fridge", "sink"))
        ]
        if not all(leg_lo <= leg <= leg_hi for leg in legs) or not sum_lo <= sum(legs) <= sum_hi:
            out.append(
                Issue(
                    "WORK_TRIANGLE",
                    "warning",
                    f"{r.name}: work triangle legs "
                    f"{', '.join(f'{leg / 1000:.1f}' for leg in legs)} m "
                    f"(each 1.2-2.7 m, total 4.0-7.9 m)",
                    [r.id],
                    "NKBA kitchen guideline",
                )
            )
    return out


def _wcs(st: Storey, names: dict[str, str]) -> list[Issue]:
    out = []
    side = CHECKS["wc_side_mm"]
    for f in st.fixtures:
        if f.kind != "wc":
            continue
        room = next((r for r in st.rooms if r.id == f.room), None)
        if room is None:
            continue
        net = _net(room, st)
        x0, y0, x1, y1 = net.bounds
        across = (x0, x1) if f.rotation in (0, 180) else (y0, y1)
        c = f.x if f.rotation in (0, 180) else f.y
        if min(c - across[0], across[1] - c) < side - 25:
            out.append(
                Issue(
                    "WC_CLEARANCE",
                    "warning",
                    f"{room.name}: the WC centre is less than {side} mm from a side wall",
                    [room.id],
                    "DBC K.5.7.2",
                )
            )
    return out


def _wet_stack(b: Building) -> list[Issue]:
    if len(b.storeys) < 2:
        return [Issue("WET_STACK", "info", "one storey: wet areas need no stacking")]
    out = []
    for lower, upper in zip(b.storeys, b.storeys[1:], strict=False):
        below = unary_union([Polygon(r.polygon) for r in lower.rooms if r.type in WET])
        for r in upper.rooms:
            if r.type not in WET:
                continue
            p = Polygon(r.polygon)
            if p.intersection(below).area < CHECKS["wet_stack_overlap"] * p.area:
                out.append(
                    Issue(
                        "WET_STACK",
                        "warning",
                        f"{r.name} on {upper.name} is not over a wet room below",
                        [r.id],
                    )
                )
    return out


def _site(b: Building) -> list[Issue]:
    from app.modules.ai.floorplan.model.build import setback_box

    out = []
    a = b.areas
    lo, hi = CHECKS["coverage"]
    if not lo <= a.coverage <= hi:
        out.append(
            Issue(
                "COVERAGE",
                "warning",
                f"coverage is {a.coverage:.1%} of the plot (aim {lo:.0%}-{hi:.0%})",
            )
        )
    x0, y0, x1, y1 = setback_box(b.site)
    inside = box(x0, y0, x1, y1).buffer(1)
    for st in b.storeys:
        for r in st.rooms:
            if not inside.contains(Polygon(r.polygon)):
                out.append(
                    Issue(
                        "SETBACK",
                        "critical",
                        f"{r.name} crosses the setback line",
                        [r.id],
                        "DBC K.5.2.4",
                    )
                )
    sb = b.site.setbacks
    dbc = CHECKS["dbc_setback_m"] * 1000
    low = [
        n
        for n, v in (("sides", min(sb.left, sb.right)), ("rear", sb.rear), ("front", sb.front))
        if 0 < v < dbc
    ]
    if low:
        out.append(
            Issue(
                "SETBACK_DBC",
                "warning",
                f"setbacks ({', '.join(low)}) are below the {CHECKS['dbc_setback_m']:g} m of DBC "
                "Table K.1 for a standalone villa (allowed only under local relaxations)",
                ref="DBC K.5.2.4 Table K.1",
            )
        )
    return out


def summary(issues: list[Issue]) -> str:
    crit = [i for i in issues if i.severity == "critical"]
    warn = [i for i in issues if i.severity == "warning"]
    if not crit and not warn:
        return "Checks: no issues."
    parts = []
    if crit:
        parts.append(f"{len(crit)} critical issue(s): " + "; ".join(i.message for i in crit[:4]))
    if warn:
        parts.append(f"{len(warn)} warning(s)")
    return "Checks: " + ". ".join(parts) + "."
