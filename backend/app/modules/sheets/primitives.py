"""Derived quantities of a plan: section 3 of docs/materials_formula_spec.md.

`PlanFacts` is what is measured from a plan (section 1): rooms, levels, openings and the
two net wall areas. `derive_primitives` turns it into `Primitives`, the symbols every
formula in section 4 is written in. Both are plain data, so the formula layer can be
tested with numbers alone, without drawing a plan.

Everything here is computed once per plan, from project-level quantities.
"""

import math
from dataclasses import dataclass

from app.modules.plans.room_types import is_open_plan_kitchen
from app.modules.sheets import constants as c


def ceil(x: float) -> int:
    """The spec's ceil (section 0): `math.ceil(round(x, 6))`.

    Rounding first keeps float noise such as 6143.0000000001 from adding a whole unit.
    """
    return math.ceil(round(x, 6))


def clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


# ------------------------------------------------------------------------------ facts


@dataclass(frozen=True)
class RoomFact:
    name: str
    kind: str  # indoor | semi_open | outdoor | void
    area: float
    perimeter: float
    boq_type: str | None = None  # indoor rooms only
    level: int = 0

    @property
    def built(self) -> bool:
        return self.kind in ("indoor", "semi_open")

    @property
    def indoor(self) -> bool:
        return self.kind == "indoor"

    @property
    def open_plan_kitchen(self) -> bool:
        """A LIVING room whose label also names a kitchen ("Living / Dining / Kitchen")."""
        return self.indoor and self.boq_type == "LIVING" and is_open_plan_kitchen(self.name)


@dataclass(frozen=True)
class LevelFact:
    built_area: float  # A_built_l
    width: float  # W_l: bounding box of built rooms (of the walls if the level has no rooms)
    depth: float  # D_l
    height: float = c.DEFAULT_WALL_HEIGHT_M  # H_l


@dataclass(frozen=True)
class OpeningFact:
    type: str  # door | window
    width: float | None = None  # None when the plan gives no width
    height: float | None = None


@dataclass(frozen=True)
class PlanFacts:
    """Section 1: what the calculator reads from a plan."""

    levels: tuple[LevelFact, ...]
    rooms: tuple[RoomFact, ...]  # rooms of every kind that have an area, in plan order
    openings: tuple[OpeningFact, ...]
    a_netwall: float  # A_netwall
    a_netwall_0: float  # A_netwall_0 (ground level)
    site_width: float = 0.0  # bounding box of every room of any kind on level 0
    site_depth: float = 0.0
    building_type: str = "villa"
    f_fc: float = 1.0  # share of dry area that gets a false ceiling
    plot_perimeter: float | None = None
    tile_a_mm: float = 600.0
    tile_b_mm: float = 600.0
    tile_waste: float = c.TILE_WASTE_STANDARD


# ------------------------------------------------------------------------- primitives


@dataclass(frozen=True)
class Primitives:
    """Section 3. Field names are the spec's symbols in snake case."""

    L: int
    a_built: float
    a_in: float
    a_ground: float
    a_netwall: float
    a_netwall_0: float
    n_door: int
    n_win: int

    a_bath: float
    p_bath: float
    n_bath: int
    n_shower: int
    a_kit: float
    p_kit: float
    n_kit: int
    a_lau: float
    p_lau: float
    n_lau: int
    a_wet: float
    p_wet: float
    a_dry: float
    n_bed: int
    n_liv: int
    n_din: int
    n_ac: int
    n_wh: int

    p_ext: tuple[float, ...]  # P_ext_l per level
    roof_level: int  # l*
    a_roof: float
    p_roof: float
    d_roof: float
    g_ext: float
    a_ext: float
    a_int: float
    a_plinth: float
    a_parapet: float
    a_masonry: float
    t_wall: float
    t_floor: float
    a_gyp_wall: float
    a_cem: float
    s_gyp: float
    s_cem: float
    e_net: float
    v_dry: float
    a_pave: float
    p_pave: float
    p_site: float
    sum_p_built: float  # sum of P_r over built rooms

    a_other: float  # indoor area typed OTHER
    a_ext_capped: bool  # A_ext was capped by A_netwall
    a_gyp_clamped: bool  # A_gyp_wall was clamped to 0
    widths_present: bool  # at least one opening carries a width
    open_plan_kitchens: int

    @property
    def p_ext_0(self) -> float:
        return self.p_ext[0] if self.p_ext else 0.0

    @property
    def has_building(self) -> int:
        """[A_built > 0]"""
        return 1 if self.a_built > 0 else 0

    @property
    def has_wet_core(self) -> int:
        """[N_bath + N_kit > 0]"""
        return 1 if self.n_bath + self.n_kit > 0 else 0


NOT_PAVED_WORDS = ("lawn", "garden", "grass", "plant", "pool")
AC_ROOM_TYPES = ("BED", "LIVING", "DINING", "STUDY", "KITCHEN", "OTHER")


def derive_primitives(facts: PlanFacts) -> Primitives:
    """Section 3, in the order the spec lists it. Pure: same facts, same primitives."""
    indoor = [r for r in facts.rooms if r.indoor]
    built = [r for r in facts.rooms if r.built]

    def of_type(boq_type: str) -> list[RoomFact]:
        return [r for r in indoor if r.boq_type == boq_type]

    baths, kitchens, laundries = of_type("BATH"), of_type("KITCHEN"), of_type("LAUNDRY")

    a_in = sum(r.area for r in indoor)
    a_built = sum(level.built_area for level in facts.levels)
    a_ground = facts.levels[0].built_area if facts.levels else 0.0

    a_bath = sum(r.area for r in baths)
    p_bath = sum(r.perimeter for r in baths)
    n_bath = len(baths)
    n_shower = sum(1 for r in baths if r.area >= c.SHOWER_MIN_BATH_AREA_M2)

    # Kitchens, plus the kitchen portion of every open-plan living space.
    a_kit = sum(r.area for r in kitchens)
    p_kit = sum(r.perimeter for r in kitchens)
    n_kit = len(kitchens)
    open_plan = [r for r in indoor if r.open_plan_kitchen]
    for room in open_plan:
        portion = min(c.OPEN_PLAN_KITCHEN_MAX_M2, room.area / 3.0)
        a_kit += portion
        p_kit += 4.0 * math.sqrt(portion)
        n_kit += 1

    a_lau = sum(r.area for r in laundries)
    p_lau = sum(r.perimeter for r in laundries)
    n_lau = len(laundries)

    a_wet = a_bath + a_kit + a_lau
    p_wet = p_bath + p_kit + p_lau
    a_dry = max(a_in - a_wet, 0.0)

    n_ac = sum(
        ceil(r.area / c.AC_AREA_PER_UNIT_M2)
        for r in indoor
        if r.boq_type in AC_ROOM_TYPES and r.area >= c.AC_MIN_ROOM_AREA_M2
    )
    n_wh = n_bath + n_kit

    # Exterior walls: bounding-box perimeter of each level; the roof is the largest level.
    p_ext = tuple(2.0 * (level.width + level.depth) for level in facts.levels)
    roof_level = 0
    for index, level in enumerate(facts.levels):
        if level.built_area > facts.levels[roof_level].built_area:
            roof_level = index
    if facts.levels:
        roof = facts.levels[roof_level]
        a_roof, p_roof, d_roof = roof.built_area, p_ext[roof_level], min(roof.width, roof.depth)
    else:
        a_roof = p_roof = d_roof = 0.0

    n_win = sum(1 for o in facts.openings if o.type == "window")
    n_door = sum(1 for o in facts.openings if o.type == "door")

    g_ext = sum(p * level.height for p, level in zip(p_ext, facts.levels, strict=True))
    a_ext_uncapped = max(g_ext - c.WINDOW_OPENING_AREA_M2 * n_win, 0.5 * g_ext)
    a_ext = min(a_ext_uncapped, facts.a_netwall)
    a_int = facts.a_netwall - a_ext
    a_plinth = c.PLINTH_WALL_FACTOR * facts.a_netwall_0
    a_parapet = c.PARAPET_HEIGHT_M * p_roof
    a_masonry = facts.a_netwall + a_plinth + a_parapet

    t_wall = c.BATH_WALL_TILE_FACTOR * p_bath + c.SPLASHBACK_TILE_FACTOR * (p_kit + p_lau)
    sum_p_built = sum(r.perimeter for r in built)
    t_floor = a_built + c.SKIRTING_HEIGHT_M * sum_p_built

    gyp_unclamped = 2.0 * a_int + a_ext - t_wall
    a_gyp_wall = max(gyp_unclamped, 0.0)
    a_cem = 2.0 * facts.a_netwall - a_gyp_wall + 2.0 * a_parapet
    s_gyp = a_gyp_wall / (2.0 * facts.a_netwall) if facts.a_netwall > 0 else 0.0
    s_cem = 1.0 - s_gyp
    e_net = a_ext + 2.0 * a_parapet
    v_dry = a_built * c.SLAB_THICKNESS_M * c.RCC_STRUCTURAL_MULTIPLIER * c.DRY_VOLUME_MULTIPLIER

    paved = [
        r
        for r in facts.rooms
        if r.kind == "outdoor" and not any(word in r.name.lower() for word in NOT_PAVED_WORDS)
    ]
    a_pave = sum(r.area for r in paved)
    p_pave = sum(r.perimeter for r in paved)
    p_site = 2.0 * (facts.site_width + facts.site_depth)

    return Primitives(
        L=len(facts.levels),
        a_built=a_built,
        a_in=a_in,
        a_ground=a_ground,
        a_netwall=facts.a_netwall,
        a_netwall_0=facts.a_netwall_0,
        n_door=n_door,
        n_win=n_win,
        a_bath=a_bath,
        p_bath=p_bath,
        n_bath=n_bath,
        n_shower=n_shower,
        a_kit=a_kit,
        p_kit=p_kit,
        n_kit=n_kit,
        a_lau=a_lau,
        p_lau=p_lau,
        n_lau=n_lau,
        a_wet=a_wet,
        p_wet=p_wet,
        a_dry=a_dry,
        n_bed=len(of_type("BED")),
        n_liv=len(of_type("LIVING")),
        n_din=len(of_type("DINING")),
        n_ac=n_ac,
        n_wh=n_wh,
        p_ext=p_ext,
        roof_level=roof_level,
        a_roof=a_roof,
        p_roof=p_roof,
        d_roof=d_roof,
        g_ext=g_ext,
        a_ext=a_ext,
        a_int=a_int,
        a_plinth=a_plinth,
        a_parapet=a_parapet,
        a_masonry=a_masonry,
        t_wall=t_wall,
        t_floor=t_floor,
        a_gyp_wall=a_gyp_wall,
        a_cem=a_cem,
        s_gyp=s_gyp,
        s_cem=s_cem,
        e_net=e_net,
        v_dry=v_dry,
        a_pave=a_pave,
        p_pave=p_pave,
        p_site=p_site,
        sum_p_built=sum_p_built,
        a_other=sum(r.area for r in of_type("OTHER")),
        a_ext_capped=a_ext_uncapped > facts.a_netwall,
        a_gyp_clamped=gyp_unclamped < 0,
        widths_present=any(o.width is not None and o.width > 0 for o in facts.openings),
        open_plan_kitchens=len(open_plan),
    )
