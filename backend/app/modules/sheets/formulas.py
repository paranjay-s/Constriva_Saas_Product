"""The 59 material formulas: section 4 of docs/materials_formula_spec.md.

    values = compute_items(primitives, facts)      # {serial: ItemValue}

Pure functions of `Primitives` and `PlanFacts`: no plan, no I/O. Each formula is written
as the spec states it, with every number taken from `constants.py`. Waste is applied once,
at the end of each formula, and `ceil` is the spec's `math.ceil(round(x, 6))`.

Items are keyed by serial: an int, or a string such as "17a" for a split item.
"""

from dataclasses import dataclass

from app.modules.sheets import constants as c
from app.modules.sheets.primitives import PlanFacts, Primitives, RoomFact, ceil, clamp

Serial = int | str

# Not built for an apartment: roof, plinth-level and site items (spec section 5).
APARTMENT_ZERO_ITEMS: tuple[Serial, ...] = (8, 10, 20, 21, 22, 23, 26, 30, 31, 58)
APARTMENT_NOTE = "Not counted for an apartment: this is a whole-building item."

PERGOLA_WORDS = ("pergola", "gazebo")
DRY_ROOM_EXCLUDED_TYPES = ("BATH", "KITCHEN", "LAUNDRY")
GENERAL_SOCKET_TYPES = ("BED", "LIVING", "DINING", "STUDY", "OTHER")


@dataclass(frozen=True)
class Part:
    """One line of an item's breakdown."""

    label: str
    quantity: float
    unit: str
    decimals: int = 0


@dataclass(frozen=True)
class ItemValue:
    quantity: float
    parts: tuple[Part, ...] = ()
    note: str = ""


def grout_factor(tile_a_mm: float, tile_b_mm: float) -> float:
    """g in kg/m2 for an a x b mm floor tile (3 mm joint, 10 mm depth)."""
    if tile_a_mm <= 0 or tile_b_mm <= 0:
        return 0.0
    return c.GROUT_FACTOR * (tile_a_mm + tile_b_mm) / (tile_a_mm * tile_b_mm)


def socket_count(room: RoomFact) -> int:
    """13 A twin sockets of one indoor room (item 33, S)."""
    if room.boq_type in GENERAL_SOCKET_TYPES:
        return max(c.SOCKETS_MIN_PER_ROOM, ceil(room.perimeter / c.SOCKET_SPACING_M))
    if room.boq_type == "KITCHEN":
        return max(c.KITCHEN_SOCKETS_MIN, ceil(room.perimeter / c.KITCHEN_SOCKET_SPACING_M))
    if room.boq_type == "BATH":
        return c.BATH_SOCKETS
    if room.boq_type == "LAUNDRY":
        return c.LAUNDRY_SOCKETS
    if room.boq_type == "CIRC":
        return ceil(room.perimeter / c.CIRCULATION_SOCKET_SPACING_M)
    if room.boq_type == "STORE":
        return c.STORE_SOCKETS
    return 0


def compute_items(p: Primitives, facts: PlanFacts) -> dict[Serial, ItemValue]:
    """Every item of the bill, at project scope."""
    indoor = [r for r in facts.rooms if r.indoor]
    semi_open = [r for r in facts.rooms if r.kind == "semi_open"]
    windows = [o for o in facts.openings if o.type == "window"]
    doors = [o for o in facts.openings if o.type == "door"]
    items: dict[Serial, ItemValue] = {}

    # ------------------------------------------------------------- Group A (1-7)
    items[1] = ItemValue(
        ceil(p.a_masonry / c.UAE_AAC_BLOCK_AREA_M2 * c.MASONRY_WASTE_FACTOR),
        (
            Part("Total masonry area", p.a_masonry, "m²", 2),
            Part("Superstructure walls", p.a_netwall, "m²", 2),
            Part("Plinth walls", p.a_plinth, "m²", 2),
            Part("Parapet walls", p.a_parapet, "m²", 2),
        ),
        "Includes 5% waste.",
    )

    steel_kg = (
        c.PLINTH_STEEL_KG_PER_M2 * p.a_ground + c.FLOOR_STEEL_KG_PER_M2 * p.a_built
    ) * c.STEEL_WASTE_FACTOR
    items[2] = ItemValue(
        steel_kg,
        (
            Part("12 m rods (12 mm average)", ceil(steel_kg / c.TMT_12MM_ROD_WEIGHT_KG), "Nos"),
            Part("Weight", steel_kg / 1000.0, "t", 2),
        ),
        "Includes 10% waste.",
    )

    items[3] = ItemValue(
        ceil(
            (
                p.v_dry / c.M20_TOTAL_PARTS * c.CEMENT_BAGS_PER_M3
                + c.MORTAR_CEMENT_BAGS_PER_M2 * p.a_masonry
                + c.EXT_PLASTER_CEMENT_BAGS_PER_M2 * p.a_cem
            )
            * c.CEMENT_WASTE_FACTOR
        ),
        (Part("Cement plaster area", p.a_cem, "m²", 2),),
        "Concrete, block mortar and cement plaster. Includes 5% waste.",
    )

    sand_m3 = (
        1.5 / c.M20_TOTAL_PARTS * p.v_dry
        + c.MORTAR_SAND_THICKNESS_M * p.a_masonry
        + c.EXT_PLASTER_SAND_THICKNESS_M * p.a_cem
        + c.TILE_BEDDING_SCREED_THICKNESS_M * p.a_built
    )
    items[4] = ItemValue(
        sand_m3,
        (Part("Weight", sand_m3 * c.SAND_BULK_DENSITY_TONS_M3 * c.SAND_WASTE_FACTOR, "t", 2),),
        "Concrete, mortar, cement plaster and floor screed. The weight includes 5% waste.",
    )

    gitti_m3 = 3.0 / c.M20_TOTAL_PARTS * p.v_dry * c.GITTI_WASTE_FACTOR
    items[5] = ItemValue(
        gitti_m3,
        (Part("Weight", gitti_m3 * c.GITTI_BULK_DENSITY_TONS_M3, "t", 2),),
        "Includes 5% waste.",
    )

    items[6] = ItemValue(
        ceil(
            (c.GYPSUM_WALL_THICKNESS_M * p.a_gyp_wall + c.GYPSUM_CEILING_THICKNESS_M * p.a_built)
            * c.GYPSUM_WASTE_FACTOR
            * c.GYPSUM_DENSITY_KG_M3
            / c.GYPSUM_BAG_WEIGHT_KG
        ),
        (
            Part("Gypsum-plastered wall faces", p.a_gyp_wall, "m²", 2),
            Part("Ceilings", p.a_built, "m²", 2),
        ),
        "Interior walls and ceilings. Includes 15% waste.",
    )

    tile_area_m2 = facts.tile_a_mm * facts.tile_b_mm / 1_000_000.0
    tiles_m2 = p.t_floor * facts.tile_waste
    items[7] = ItemValue(
        tiles_m2,
        (
            Part(
                f"Tiles {facts.tile_a_mm:g} x {facts.tile_b_mm:g} mm",
                ceil(tiles_m2 / tile_area_m2) if tile_area_m2 > 0 else 0,
                "pieces",
            ),
        ),
        f"Floor area plus 100 mm skirting. Includes {(facts.tile_waste - 1) * 100:.0f}% waste.",
    )

    # ------------------------------------------------------------ Group B (8-23)
    roof_with_upstand = p.a_roof + c.ROOF_UPSTAND_M * p.p_roof
    items[8] = ItemValue(roof_with_upstand * c.PU_FOAM_WASTE)

    items[9] = ItemValue(
        ceil(
            (
                c.BITUMEN_ROOF_PRIMER_L_PER_M2 * p.a_roof
                + c.BITUMEN_PLINTH_L_PER_M2
                * (2.0 * p.a_plinth + c.FOOTING_SHARE_OF_FOOTPRINT * p.a_ground)
            )
            * c.BITUMEN_WASTE
        ),
        note="Roof primer, plus two coats on both faces of plinth walls and on footings.",
    )

    screed_t = clamp(
        c.SCREED_BASE_THICKNESS_M + c.SCREED_SLOPE_M_PER_M * p.d_roof,
        c.SCREED_MIN_THICKNESS_M,
        c.SCREED_MAX_THICKNESS_M,
    )
    items[10] = ItemValue(
        p.a_roof * screed_t * c.SCREED_WASTE,
        (Part("Average thickness", screed_t * 1000.0, "mm"),) if p.a_roof > 0 else (),
    )

    items[11] = ItemValue(
        ceil(
            (
                c.WATERPROOF_ROOF_KG_PER_M2 * roof_with_upstand
                + c.WATERPROOF_WET_KG_PER_M2
                * (p.a_wet + c.WET_AREA_UPSTAND_M * p.p_wet + c.SHOWER_WALL_AREA_M2 * p.n_shower)
            )
            * c.WATERPROOF_WASTE
        ),
        note="Roof, wet-area floors with upstands, and shower walls.",
    )

    items[12] = ItemValue(
        p.t_wall * c.WALL_TILE_WASTE,
        note="Wall tiles only: baths to 2.40 m, splashbacks in kitchens and laundries. "
        "Wet-area floors are in item 7.",
    )

    g = grout_factor(facts.tile_a_mm, facts.tile_b_mm)
    items[13] = ItemValue(
        ceil((g * p.t_floor + c.GROUT_WALL_KG_PER_M2 * p.t_wall) * c.GROUT_WASTE),
        note="3 mm joints, 10 mm deep, for floor and wall tiles.",
    )

    items[14] = ItemValue(ceil(c.SOLVENT_L_PER_M2 * p.a_built))

    sill_length = sum(
        (o.width if o.width else c.DEFAULT_WINDOW_WIDTH_M) + c.WINDOW_SILL_OVERHANG_M
        for o in windows
    )
    thresholds = c.THRESHOLD_LENGTH_M * (p.n_bath + p.n_kit + p.n_lau + p.has_building)
    items[15] = ItemValue(
        (thresholds + sill_length) * c.STONE_WASTE,
        (
            Part("Door thresholds", thresholds, "LM", 2),
            Part("Window sills", sill_length, "LM", 2),
        ),
    )

    items[16] = ItemValue(
        (c.NICHE_M2_PER_SHOWER * p.n_shower + c.NICHE_M2_PER_LIVING_ROOM * p.n_liv) * c.NICHE_WASTE
    )

    items["17a"] = ItemValue(
        ceil(p.a_gyp_wall * c.PAINT_COATS / c.INTERIOR_PAINT_M2_PER_L * c.PAINT_WASTE),
        (Part("Painted wall faces", p.a_gyp_wall, "m²", 2),),
        "Two coats.",
    )
    items["17b"] = ItemValue(ceil(p.a_gyp_wall / c.PRIMER_M2_PER_L * c.PAINT_WASTE))

    mr_board_m2 = c.GYPSUM_BOARD_WASTE * p.a_wet
    items["18a"] = ItemValue(
        mr_board_m2,
        (Part("Boards 1.2 x 2.4 m", ceil(mr_board_m2 / c.GYPSUM_BOARD_AREA_M2), "Nos"),),
        "Moisture-resistant board over wet areas.",
    )
    regular_board_m2 = c.GYPSUM_BOARD_WASTE * facts.f_fc * p.a_dry
    items["18b"] = ItemValue(
        regular_board_m2,
        (Part("Boards 1.2 x 2.4 m", ceil(regular_board_m2 / c.GYPSUM_BOARD_AREA_M2), "Nos"),),
        f"False ceiling over {facts.f_fc * 100:.0f}% of the dry indoor area.",
    )

    items[19] = ItemValue(
        ceil(p.a_built * c.PAINT_COATS / c.INTERIOR_PAINT_M2_PER_L * c.PAINT_WASTE),
        note="Two coats.",
    )
    items[20] = ItemValue(p.e_net * c.EXTERIOR_PLASTER_WASTE)
    items[21] = ItemValue(
        ceil(p.e_net * c.PAINT_COATS / c.EXTERIOR_PAINT_M2_PER_L * c.PAINT_WASTE),
        note="Two coats.",
    )
    # A row that is 0 because the plan does not show the thing says so in its note.
    no_paving = "" if p.a_pave > 0 else "0 because the plan shows no paved outdoor area."
    items[22] = ItemValue(p.a_pave * c.PAVING_WASTE, note=no_paving)
    kerb_lm = c.KERB_SHARE_OF_PERIMETER * p.p_pave * c.KERB_WASTE
    items[23] = ItemValue(
        kerb_lm,
        (Part("Kerb pieces 915 mm", ceil(kerb_lm / c.KERB_PIECE_LENGTH_M), "Nos"),)
        if kerb_lm > 0
        else (),
        no_paving,
    )

    # ----------------------------------------------------------- Group C (24-31)
    items[24] = ItemValue(p.n_ac + p.n_bath)
    items[25] = ItemValue(ceil(p.n_ac / c.AC_UNITS_PER_CANOPY))
    items[26] = ItemValue(p.has_building)
    items[27] = ItemValue(p.n_bath + p.n_lau)

    no_widths = "" if p.widths_present else "0 because the plan gives no opening widths."
    curtain_wall_m2 = sum(
        o.width * (o.height if o.height else c.CURTAIN_WALL_DEFAULT_HEIGHT_M)
        for o in windows
        if o.width and o.width >= c.CURTAIN_WALL_MIN_WIDTH_M
    )
    items[28] = ItemValue(
        curtain_wall_m2,
        note=no_widths
        or (
            "Windows 2.20 m wide or more."
            if curtain_wall_m2 > 0
            else "0 because no window is 2.20 m wide or more."
        ),
    )
    glass_doors = sum(1 for o in doors if o.width and o.width >= c.GLASS_DOOR_MIN_WIDTH_M)
    items[29] = ItemValue(
        glass_doors,
        note=no_widths
        or (
            "Doors 1.40 m wide or more."
            if glass_doors > 0
            else "0 because no door is 1.40 m wide or more."
        ),
    )
    pergola_m2 = sum(
        r.area for r in facts.rooms if any(word in r.name.lower() for word in PERGOLA_WORDS)
    )
    items[30] = ItemValue(
        pergola_m2, note="" if pergola_m2 > 0 else "0 because no room is named pergola or gazebo."
    )
    items[31] = ItemValue(c.GATE_SETS * p.has_building)

    # ----------------------------------------------------------- Group D (32-43)
    cable_lm = ceil(p.a_built * c.CABLE_M_PER_M2 * c.CABLE_WASTE)
    items[32] = ItemValue(
        cable_lm,
        (Part("Coils of 91.4 m", ceil(cable_lm / c.CABLE_COIL_LENGTH_M), "Nos"),),
        "For purchasing: 35% lighting, 40% sockets, 20% AC and heaters, 5% cooker.",
    )

    sockets = sum(socket_count(r) for r in indoor) + (
        c.OPEN_PLAN_KITCHEN_SOCKETS * p.open_plan_kitchens
    )
    switches = sum(1 + (1 if r.area > c.SECOND_SWITCH_MIN_AREA_M2 else 0) for r in indoor)
    dp_switches = p.n_wh + p.n_kit
    items[33] = ItemValue(
        sockets + switches + dp_switches,
        (
            Part("13 A twin sockets", sockets, "Nos"),
            Part("Light switches", switches, "Nos"),
            Part("Heater and cooker switches", dp_switches, "Nos"),
        ),
    )

    n_db = (p.L + (1 if p.L >= 2 else 0)) * p.has_building
    items[34] = ItemValue(n_db)

    spotlights = (
        sum(
            ceil(r.area / c.SPOTLIGHT_AREA_DRY_M2)
            for r in indoor
            if r.boq_type not in DRY_ROOM_EXCLUDED_TYPES
        )
        + sum(
            ceil(r.area / c.SPOTLIGHT_AREA_WET_M2)
            for r in indoor
            if r.boq_type in ("KITCHEN", "LAUNDRY")
        )
        + sum(ceil(r.area / c.SPOTLIGHT_AREA_SEMI_OPEN_M2) for r in semi_open)
    )
    chandeliers = p.n_liv + p.n_din + ceil(p.n_bed / 2)
    bath_lights = sum(
        max(1, ceil(r.area / c.BATH_LIGHT_AREA_M2)) for r in indoor if r.boq_type == "BATH"
    )
    lights = spotlights + chandeliers + bath_lights  # Lt

    circuit_breakers = (
        ceil(sockets / c.SOCKETS_PER_CIRCUIT)
        + ceil(lights / c.LIGHTS_PER_CIRCUIT)
        + p.n_ac
        + p.n_wh
        + p.n_kit
    )
    board_devices = c.DEVICES_PER_DISTRIBUTION_BOARD * n_db
    isolators = p.n_ac + p.n_wh
    items[35] = ItemValue(
        circuit_breakers + board_devices + isolators,
        (
            Part("Circuit breakers", circuit_breakers, "Nos"),
            Part("Main devices, 3 per distribution board", board_devices, "Nos"),
            Part("Isolators for AC units and water heaters", isolators, "Nos"),
        ),
    )

    items[36] = ItemValue(spotlights)
    items[37] = ItemValue(p.n_bath + p.n_kit)
    items[38] = ItemValue(p.n_wh)
    items[39] = ItemValue(chandeliers)
    items[40] = ItemValue(bath_lights)

    led_strip = (
        c.LED_STRIP_SHARE_OF_PERIMETER
        * sum(r.perimeter for r in indoor if r.boq_type in ("LIVING", "BED"))
        + c.LED_STRIP_M_PER_BATH * p.n_bath
    ) * c.LED_STRIP_WASTE
    items[41] = ItemValue(led_strip, note="Living rooms and bedrooms, plus bathroom mirrors.")
    items[42] = ItemValue(led_strip, note="Same length as the LED strip (item 41).")
    items[43] = ItemValue(p.n_ac)

    # ----------------------------------------------------------- Group E (44-57)
    items[44] = ItemValue(p.n_ac * c.AC_DRAIN_M_PER_UNIT * c.AC_DRAIN_WASTE)
    items[45] = ItemValue(
        c.ANGLE_VALVES_PER_BATH * p.n_bath
        + c.ANGLE_VALVES_PER_KITCHEN * p.n_kit
        + c.ANGLE_VALVES_PER_LAUNDRY * p.n_lau
    )
    items[46] = ItemValue(
        c.ISOLATION_VALVES_PER_WET_ROOM * (p.n_bath + p.n_kit)
        + c.ISOLATION_VALVES_MAIN * p.has_wet_core
    )
    items["47a"] = ItemValue(p.n_bath)
    items["47b"] = ItemValue(c.HOSE_BIBS * p.has_building)
    items[48] = ItemValue(p.n_bath + p.n_kit)
    items[49] = ItemValue(p.n_shower)
    items[50] = ItemValue(p.n_bath)
    items[51] = ItemValue(c.PUMP_SETS * p.has_wet_core)

    tanks = c.WATER_TANKS * p.has_wet_core
    bedrooms = max(1, p.n_bed)
    ground_tank_l = c.TANK_SIZE_STEP_L * ceil(
        c.GROUND_TANK_L_PER_BEDROOM * bedrooms / c.TANK_SIZE_STEP_L
    )
    roof_tank_l = c.TANK_SIZE_STEP_L * ceil(
        c.ROOF_TANK_L_PER_BEDROOM * bedrooms / c.TANK_SIZE_STEP_L
    )
    items[52] = ItemValue(
        tanks,
        (Part("Ground tank", ground_tank_l, "L"), Part("Roof tank", roof_tank_l, "L"))
        if tanks
        else (),
        "One ground tank and one roof tank." if tanks else "",
    )

    items["53a"] = ItemValue(p.n_bath + p.n_shower + p.n_kit + p.n_lau)
    items["53b"] = ItemValue(
        max(c.ROOF_OUTLETS_MIN, ceil(p.a_roof / c.ROOF_AREA_PER_OUTLET_M2)) if p.a_roof > 0 else 0
    )
    items[54] = ItemValue(p.n_bath + p.n_kit)
    items[55] = ItemValue(p.n_bath)
    items[56] = ItemValue(p.n_bath + p.n_kit)
    items["57a"] = ItemValue(ceil((p.n_bath + p.n_kit) / 2))
    items["57b"] = ItemValue(
        max(c.MANHOLES_MIN, ceil(p.p_ext_0 / c.MANHOLE_SPACING_M)) * p.has_wet_core
    )

    # ----------------------------------------------------------- Group F (58-59)
    if facts.plot_perimeter is not None and facts.plot_perimeter > 0:
        items[58] = ItemValue(facts.plot_perimeter, note="The plot perimeter that was supplied.")
    elif p.p_site <= 0 and p.p_ext_0 <= 0:
        # An empty plan: section 7 of the spec says every item is then 0.
        items[58] = ItemValue(0.0)
    else:
        items[58] = ItemValue(
            max(p.p_site, p.p_ext_0 + c.HOARDING_OFFSET_M) * c.HOARDING_WASTE,
            note="Estimated from the plan outline. Supply the plot perimeter to replace it.",
        )
    items[59] = ItemValue(p.has_building)

    if facts.building_type == "apartment":
        for serial in APARTMENT_ZERO_ITEMS:
            items[serial] = ItemValue(0, note=APARTMENT_NOTE)
    return items


def calculation_warnings(p: Primitives, facts: PlanFacts) -> list[str]:
    """The warnings of spec section 6, in a fixed order."""
    if p.a_built <= 0:
        return ["No built area was found in the plan, so building quantities are zero."]
    apartment = facts.building_type == "apartment"
    warnings: list[str] = []
    if p.n_bath == 0 and p.n_kit == 0:
        warnings.append(
            "No bathroom or kitchen was detected, so plumbing and wet-area items are 0. "
            "Check the room labels."
        )
    elif p.n_bath == 0:
        warnings.append("No bathroom was detected, so bathroom items are 0. Check the room labels.")
    elif p.n_kit == 0:
        warnings.append("No kitchen was detected, so kitchen items are 0. Check the room labels.")
    if p.a_in > 0 and p.a_other / p.a_in > 0.30:
        warnings.append(
            f"{p.a_other / p.a_in:.0%} of the indoor area has no recognised room type. "
            "Room-based quantities may be low."
        )
    if facts.openings and not p.widths_present:
        warnings.append("Opening widths are absent, so items 28 and 29 are 0.")
    if p.a_pave <= 0 and not apartment:
        warnings.append("No paved outdoor rooms were found, so items 22 and 23 are 0.")
    if facts.covered_parking:
        warnings.append(
            "Parking under an upper floor is counted as paved outdoor area, so slab "
            f"quantities exclude it: {', '.join(facts.covered_parking)}."
        )
    if p.a_ext_capped:
        warnings.append(
            "The exterior wall area was capped by the net wall area. "
            "Interior wall quantities may be low."
        )
    if p.a_gyp_clamped:
        warnings.append("The gypsum-plastered wall area was clamped to 0.")
    if apartment:
        warnings.append(
            "Apartment: items 8, 10, 20, 21, 22, 23, 26, 30, 31 and 58 are 0. "
            "Composite items (such as cement, sand, bitumen and waterproofing) still include "
            "roof and plinth terms."
        )
    return warnings
