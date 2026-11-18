"""docs/materials_formula_spec.md: derived quantities, the 59 formulas, warnings, edge cases.

The fixture of section 8 is primitives only (it is not a drawable layout), so it is
tested on the formula layer: `derive_primitives` and `compute_items`. The edge cases of
section 7 go through the calculator (`map_plan_to_materials`) with small drawn plans.
"""

import dataclasses
import json
import math
import os
from pathlib import Path

import pytest

from app.modules.parsing.normalise import normalise_plan
from app.modules.sheets import constants as c
from app.modules.sheets.boq_export import format_quantity
from app.modules.sheets.boq_rows import CATALOG, build_boq_rows, category_of
from app.modules.sheets.formulas import (
    APARTMENT_ZERO_ITEMS,
    calculation_warnings,
    compute_items,
    grout_factor,
)
from app.modules.sheets.llm_mapper import _compute_7_materials_for_scope, map_plan_to_materials
from app.modules.sheets.primitives import (
    LevelFact,
    OpeningFact,
    PlanFacts,
    RoomFact,
    ceil,
    clamp,
    derive_primitives,
)

# ------------------------------------------------------------------ section 8 fixture

FIXTURE_ROOMS = (
    ("Bed 1", "BED", 20, 18),
    ("Bed 2", "BED", 16, 16),
    ("Bed 3", "BED", 16, 16),
    ("Living", "LIVING", 36, 24),
    ("Dining", "DINING", 16, 16),
    ("Study", "STUDY", 10, 13),
    ("Kitchen", "KITCHEN", 12, 14),
    ("Bath 1", "BATH", 4.5, 8.6),
    ("Bath 2", "BATH", 4.5, 8.6),
    ("Powder", "BATH", 2.0, 6.0),
    ("Laundry", "LAUNDRY", 4, 8),
    ("Corridor", "CIRC", 14, 18),
    ("Store", "STORE", 5, 9),
)


def fixture_facts(**changes) -> PlanFacts:
    facts = PlanFacts(
        levels=(LevelFact(built_area=160, width=10, depth=16, height=3.35),),
        rooms=tuple(RoomFact(n, "indoor", a, p, t) for n, t, a, p in FIXTURE_ROOMS),
        openings=(OpeningFact("window"),) * 12 + (OpeningFact("door"),) * 13,
        a_netwall=520,
        a_netwall_0=520,
        site_width=10,
        site_depth=16,
        building_type="villa",
        f_fc=1.0,
        tile_a_mm=600,
        tile_b_mm=600,
        tile_waste=1.05,
    )
    return dataclasses.replace(facts, **changes)


EXPECTED_DERIVED = {
    "sum_p_built": 175.2,
    "n_bath": 3,
    "n_shower": 2,
    "p_bath": 23.2,
    "a_wet": 27,
    "p_wet": 45.2,
    "a_dry": 133,
    "n_bed": 3,
    "n_liv": 1,
    "n_din": 1,
    "n_kit": 1,
    "n_lau": 1,
    "n_ac": 7,
    "n_wh": 4,
    "p_ext_0": 52,
    "p_roof": 52,
    "p_site": 52,
    "d_roof": 10,
    "a_roof": 160,
    "g_ext": 174.2,
    "a_ext": 156.92,
    "a_int": 363.08,
    "a_plinth": 130,
    "a_parapet": 52,
    "a_masonry": 702,
    "t_wall": 54.624,
    "t_floor": 177.52,
    "a_gyp_wall": 828.456,
    "a_cem": 315.544,
    "e_net": 260.92,
    "v_dry": 38.2536,
}

# serial -> expected quantity, exactly as section 8 lists it
EXPECTED_ITEMS = {
    1: 6143,
    2: 9856,
    3: 331,
    4: 28.536592,
    5: 21.90888,
    6: 418,
    7: 186.396,
    8: 184.38,
    9: 229,
    10: 12.60,
    11: 295,
    12: 60.0864,
    13: 49,
    14: 13,
    15: 22.05,
    16: 2.53,
    "17a": 194,
    "17b": 87,
    "18a": 29.70,
    "18b": 146.30,
    19: 38,
    20: 273.966,
    21: 85,
    22: 0,
    23: 0,
    24: 10,
    25: 4,
    26: 1,
    27: 4,
    28: 0,
    29: 0,
    30: 0,
    31: 2,
    32: 2552,
    33: 61,
    34: 1,
    35: 40,
    36: 56,
    37: 4,
    38: 4,
    39: 4,
    40: 7,
    41: 66.15,
    42: 66.15,
    43: 7,
    44: 62.475,
    45: 24,
    46: 12,
    "47a": 3,
    "47b": 2,
    48: 4,
    49: 2,
    50: 3,
    51: 2,
    52: 2,
    "53a": 7,
    "53b": 3,
    54: 4,
    55: 3,
    56: 4,
    "57a": 2,
    "57b": 5,
    58: 79.80,
    59: 1,
}


def parts(item) -> dict[str, float]:
    return {part.label: part.quantity for part in item.parts}


def test_fixture_derived_quantities():
    p = derive_primitives(fixture_facts())
    for name, expected in EXPECTED_DERIVED.items():
        assert getattr(p, name) == pytest.approx(expected, abs=1e-9), name
    assert (p.L, p.a_built, p.a_in, p.a_ground) == (1, 160, 160, 160)
    assert (p.n_win, p.n_door, p.roof_level) == (12, 13, 0)
    assert p.s_gyp == pytest.approx(828.456 / 1040) and p.s_gyp + p.s_cem == 1.0


def test_fixture_identity_cement_plaster_is_exterior_plus_wet_walls():
    p = derive_primitives(fixture_facts())
    assert not p.a_gyp_clamped
    assert p.a_cem == pytest.approx(p.e_net + p.t_wall, abs=1e-9)


def test_fixture_every_item_matches_the_spec():
    facts = fixture_facts()
    items = compute_items(derive_primitives(facts), facts)
    assert set(items) == set(EXPECTED_ITEMS)
    for serial, expected in EXPECTED_ITEMS.items():
        assert items[serial].quantity == pytest.approx(expected, abs=1e-9), serial


def test_fixture_breakdowns_match_the_spec():
    facts = fixture_facts()
    items = compute_items(derive_primitives(facts), facts)
    assert parts(items[2])["12 m rods (12 mm average)"] == 925
    assert round(parts(items[4])["Weight"], 2) == 46.44
    assert round(parts(items[5])["Weight"], 2) == 32.86
    assert parts(items[7])["Tiles 600 x 600 mm"] == 518
    assert parts(items["18a"])["Boards 1.2 x 2.4 m"] == 11
    assert parts(items["18b"])["Boards 1.2 x 2.4 m"] == 51
    assert parts(items[32])["Coils of 91.4 m"] == 28
    assert list(parts(items[33]).values()) == [42, 14, 5]  # S + SW + DP = 61
    assert list(parts(items[35]).values()) == [26, 3, 11]  # 40
    assert parts(items[52]) == {"Ground tank": 2000, "Roof tank": 1500}
    assert "35% lighting, 40% sockets, 20% AC and heaters, 5% cooker" in items[32].note


def test_a_row_that_is_zero_because_the_plan_shows_nothing_says_why():
    facts = fixture_facts()
    items = compute_items(derive_primitives(facts), facts)
    assert items[22].note == items[23].note == "0 because the plan shows no paved outdoor area."
    assert items[28].note == items[29].note == "0 because the plan gives no opening widths."
    assert items[30].note == "0 because no room is named pergola or gazebo."

    sized = fixture_facts(openings=(OpeningFact("window", 2.1, 1.2), OpeningFact("door", 1.0, 2.1)))
    items = compute_items(derive_primitives(sized), sized)
    assert (items[28].quantity, items[28].note) == (
        0,
        "0 because no window is 2.20 m wide or more.",
    )
    assert (items[29].quantity, items[29].note) == (0, "0 because no door is 1.40 m wide or more.")

    wide = fixture_facts(openings=(OpeningFact("window", 2.4, 2.0), OpeningFact("door", 1.6, 2.1)))
    items = compute_items(derive_primitives(wide), wide)
    assert items[28].note == "Windows 2.20 m wide or more."
    assert items[29].note == "Doors 1.40 m wide or more."


def test_fixture_warnings():
    facts = fixture_facts()
    assert calculation_warnings(derive_primitives(facts), facts) == [
        "Opening widths are absent, so items 28 and 29 are 0.",
        "No paved outdoor rooms were found, so items 22 and 23 are 0.",
    ]


def test_fixture_rows_units_types_and_display():
    facts = fixture_facts()
    rows = build_boq_rows(compute_items(derive_primitives(facts), facts))
    assert len(rows) == 64
    by_serial = {r["serial_no"]: r for r in rows}
    shown = {
        s: format_quantity(r["quantity"], r["quantity_decimals"]) for s, r in by_serial.items()
    }
    assert (shown[1], by_serial[1]["unit"]) == ("6,143", "pieces")
    assert (shown[2], by_serial[2]["unit"]) == ("9,856.00", "kg")
    assert (shown[3], by_serial[3]["unit"]) == ("331", "50 kg bags")
    assert (shown[4], shown[5]) == ("28.54", "21.91")  # exact value kept, shown to 2 places
    assert by_serial[4]["quantity"] == 28.536592 and by_serial[5]["quantity"] == 21.90888
    assert (shown[6], by_serial[6]["unit"]) == ("418", "30 kg bags")
    assert (shown[7], shown[10], shown[12]) == ("186.40", "12.60", "60.09")
    assert (shown["18a"], shown["18b"], shown[20]) == ("29.70", "146.30", "273.97")
    assert (shown[32], by_serial[32]["unit"]) == ("2,552", "LM")
    assert (shown[41], shown[44], shown[58]) == ("66.15", "62.48", "79.80")
    assert (by_serial[49]["unit"], by_serial[59]["unit"]) == ("Sets", "No.")
    tank = {part["label"]: part for part in by_serial[52]["components"]}
    assert (tank["Ground tank"]["quantity"], tank["Ground tank"]["unit"]) == (2000, "L")


def test_fixture_through_the_scope_engine_gives_the_same_core_materials():
    """Items 1 to 7 from `_compute_7_materials_for_scope` at project scope."""
    p = derive_primitives(fixture_facts())
    mats = _compute_7_materials_for_scope(
        a_built_m2=p.a_built,
        a_ground_share_m2=p.a_ground,
        a_net_wall_m2=p.a_netwall,
        a_plinth_wall_m2=p.a_plinth,
        a_parapet_wall_m2=p.a_parapet,
        a_skirting_m2=c.SKIRTING_HEIGHT_M * p.sum_p_built,
        w_pattern=1.05,
        single_tile_area_m2=0.36,
        tile_size_mm="600x600",
        pattern_key="standard",
        s_gyp=p.s_gyp,
        s_cem=p.s_cem,
    )
    assert mats["aac_blocks"]["quantity"] == 6143
    assert mats["steel_rebar"]["details"]["total_steel_kg"] == 9856.0
    assert mats["steel_rebar"]["secondary_quantity"] == 925
    assert mats["cement"]["quantity"] == 331
    assert (mats["sand"]["quantity"], mats["sand"]["secondary_quantity"]) == (46.44, 28.54)
    gitti = mats["ballast_gitti"]
    assert (gitti["quantity"], gitti["secondary_quantity"]) == (32.86, 21.91)
    assert mats["plaster"]["quantity"] == 418
    assert mats["plaster"]["details"]["internal_gypsum_wall_area_m2"] == 828.46
    assert mats["plaster"]["details"]["external_wet_cement_plaster_area_m2"] == 315.54
    assert (mats["tiles"]["quantity"], mats["tiles"]["secondary_quantity"]) == (518, 186.4)


# ------------------------------------------------------------------ conventions


def test_ceil_ignores_float_noise_and_clamp_bounds():
    assert ceil(6143.0000000001) == 6143
    assert ceil(6143.00001) == 6144
    assert ceil(0.1 + 0.2 - 0.3) == 0
    assert (clamp(0.02, 0.06, 0.15), clamp(0.5, 0.06, 0.15), clamp(0.1, 0.06, 0.15)) == (
        0.06,
        0.15,
        0.1,
    )


def test_grout_factor_by_tile_size():
    assert grout_factor(600, 600) == pytest.approx(0.17)
    assert grout_factor(800, 800) == pytest.approx(0.1275)
    assert grout_factor(1200, 600) == pytest.approx(0.1275)
    assert grout_factor(300, 600) == pytest.approx(c.GROUT_WALL_KG_PER_M2)
    assert grout_factor(0, 600) == 0.0


def test_screed_thickness_is_clamped():
    def screed(d_roof: float) -> float:
        facts = fixture_facts(levels=(LevelFact(160, d_roof, 40.0, 3.35),))
        return compute_items(derive_primitives(facts), facts)[10].quantity

    assert screed(2.0) == pytest.approx(160 * 0.06 * 1.05)  # 0.055 -> floor of 0.06
    assert screed(10.0) == pytest.approx(160 * 0.075 * 1.05)
    assert screed(40.0) == pytest.approx(160 * 0.15 * 1.05)  # depth 40: 0.15 cap


def test_catalog_lists_every_row_of_the_spec():
    serials = [item.serial for item in CATALOG]
    assert len(serials) == len(set(serials)) == 64
    assert {int(str(s).rstrip("ab")) for s in serials} == set(range(1, 60))
    assert [s for s in serials if isinstance(s, str)] == [
        "17a",
        "17b",
        "18a",
        "18b",
        "47a",
        "47b",
        "53a",
        "53b",
        "57a",
        "57b",
    ]
    assert {item.serial for item in CATALOG if item.excluded} == {22, 23, 30, 31, 52, 56}
    allowances = {item.serial for item in CATALOG if item.calc_type == "allowance"}
    assert allowances == {14, 16, 25, 31, 39, 41, 42}
    assert len({item.item_code for item in CATALOG}) == 64
    for item in CATALOG:
        assert category_of(item.serial)  # every row has a category and a sub-category
    assert category_of("17a") == category_of("17b") == category_of(17)
    assert category_of("18b")[2] == "Ceilings" and category_of("53a")[2] == "Drainage"


def test_tile_size_and_pattern_change_only_what_depends_on_them():
    plain = fixture_facts()
    large = fixture_facts(tile_a_mm=800, tile_b_mm=800, tile_waste=1.15)
    a = compute_items(derive_primitives(plain), plain)
    b = compute_items(derive_primitives(large), large)
    assert b[7].quantity == pytest.approx(177.52 * 1.15)
    assert parts(b[7])["Tiles 800 x 800 mm"] == math.ceil(177.52 * 1.15 / 0.64)
    assert b[13].quantity == ceil((0.1275 * 177.52 + 0.255 * 54.624) * 1.10)
    changed = {serial for serial in a if a[serial] != b[serial]}
    assert changed == {7, 13}


def test_optional_inputs_false_ceiling_share_and_plot_perimeter():
    facts = fixture_facts(f_fc=0.5, plot_perimeter=120.0)
    items = compute_items(derive_primitives(facts), facts)
    assert items["18b"].quantity == pytest.approx(1.10 * 0.5 * 133)
    assert items["18a"].quantity == pytest.approx(29.70)  # wet areas are always boarded
    assert items[58].quantity == 120.0


def test_opening_sizes_drive_sills_curtain_wall_and_glass_doors():
    openings = (
        OpeningFact("window", 2.4, 2.0),  # curtain wall, its own height
        OpeningFact("window", 2.2),  # curtain wall, default height 2.40
        OpeningFact("window", 1.2, 1.2),
        OpeningFact("window"),  # no width: sill uses 1.20
        OpeningFact("door", 1.5, 2.1),  # glass door
        OpeningFact("door", 0.9, 2.1),
        OpeningFact("door"),
    )
    facts = fixture_facts(openings=openings)
    p = derive_primitives(facts)
    items = compute_items(p, facts)
    assert items[28].quantity == pytest.approx(2.4 * 2.0 + 2.2 * 2.4)
    assert items[29].quantity == 1
    sills = (2.4 + 0.1) + (2.2 + 0.1) + (1.2 + 0.1) + (1.2 + 0.1)
    assert items[15].quantity == pytest.approx((0.9 * 6 + sills) * 1.05)
    assert "Opening widths are absent, so items 28 and 29 are 0." not in calculation_warnings(
        p, facts
    )


def test_paved_outdoor_rooms_and_pergola():
    outdoor = (
        RoomFact("Driveway", "outdoor", 30.0, 22.0),
        RoomFact("Parking", "outdoor", 18.0, 18.0),
        RoomFact("Front Lawn", "outdoor", 40.0, 26.0),  # not paved
        RoomFact("Swimming Pool", "outdoor", 25.0, 20.0),  # not paved
        RoomFact("Pergola", "outdoor", 12.0, 14.0),  # paved, and a pergola
    )
    facts = fixture_facts(rooms=fixture_facts().rooms + outdoor)
    p = derive_primitives(facts)
    assert (p.a_pave, p.p_pave) == (60.0, 54.0)
    items = compute_items(p, facts)
    assert items[22].quantity == pytest.approx(63.0)
    assert items[23].quantity == pytest.approx(0.75 * 54 * 1.05)
    assert parts(items[23])["Kerb pieces 915 mm"] == ceil(0.75 * 54 * 1.05 / 0.915)
    assert items[30].quantity == 12.0
    assert p.a_built == 160 and p.a_in == 160  # outdoor rooms add no built area
    assert not any("items 22 and 23" in w for w in calculation_warnings(p, facts))


# ------------------------------------------------------------------ warnings (section 6)


def test_warning_when_the_exterior_wall_area_is_capped():
    facts = fixture_facts(a_netwall=100, a_netwall_0=100)
    p = derive_primitives(facts)
    assert p.a_ext_capped and (p.a_ext, p.a_int) == (100, 0)
    assert any("capped by the net wall area" in w for w in calculation_warnings(p, facts))


def test_warning_when_the_gypsum_wall_area_is_clamped():
    facts = fixture_facts(a_netwall=20, a_netwall_0=20)
    p = derive_primitives(facts)
    # 2 x 0 + 20 - 54.624 is negative
    assert p.a_gyp_clamped and p.a_gyp_wall == 0
    assert (p.s_gyp, p.s_cem) == (0.0, 1.0)
    assert p.a_cem == pytest.approx(2 * 20 + 2 * 52)
    assert "The gypsum-plastered wall area was clamped to 0." in calculation_warnings(p, facts)
    items = compute_items(p, facts)
    assert items["17a"].quantity == 0 and items["17b"].quantity == 0


def test_warning_when_most_indoor_area_has_no_room_type():
    rooms = (
        RoomFact("Room 1", "indoor", 40.0, 26.0, "OTHER"),
        RoomFact("Bedroom", "indoor", 60.0, 32.0, "BED"),
        RoomFact("Bath", "indoor", 5.0, 9.0, "BATH"),
        RoomFact("Kitchen", "indoor", 10.0, 13.0, "KITCHEN"),
    )
    facts = fixture_facts(rooms=rooms)
    warnings = calculation_warnings(derive_primitives(facts), facts)
    assert warnings[0].startswith("35% of the indoor area has no recognised room type")
    below = fixture_facts(rooms=rooms[1:] + (RoomFact("Room 1", "indoor", 20.0, 18.0, "OTHER"),))
    assert not any("room type" in w for w in calculation_warnings(derive_primitives(below), below))


def test_warnings_for_a_missing_bathroom_or_kitchen():
    def warn(*rooms) -> list[str]:
        facts = fixture_facts(rooms=rooms)
        return calculation_warnings(derive_primitives(facts), facts)

    bed = RoomFact("Bedroom", "indoor", 20.0, 18.0, "BED")
    bath = RoomFact("Bath", "indoor", 5.0, 9.0, "BATH")
    kitchen = RoomFact("Kitchen", "indoor", 10.0, 13.0, "KITCHEN")
    assert warn(bed)[0].startswith("No bathroom or kitchen was detected")
    assert warn(bed, kitchen)[0].startswith("No bathroom was detected")
    assert warn(bed, bath)[0].startswith("No kitchen was detected")
    assert not any("was detected" in w for w in warn(bed, bath, kitchen))


# ------------------------------------------------------------------ apartment rule


def test_apartment_rule_zeroes_whole_building_items_with_a_note_and_a_warning():
    villa = fixture_facts()
    flat = fixture_facts(building_type="apartment")
    a = compute_items(derive_primitives(villa), villa)
    b = compute_items(derive_primitives(flat), flat)
    assert set(APARTMENT_ZERO_ITEMS) == {8, 10, 20, 21, 22, 23, 26, 30, 31, 58}
    for serial in APARTMENT_ZERO_ITEMS:
        assert b[serial].quantity == 0 and "apartment" in b[serial].note
    for serial in a:
        if serial not in APARTMENT_ZERO_ITEMS:
            assert b[serial] == a[serial], serial  # composite items keep roof and plinth terms
    warnings = calculation_warnings(derive_primitives(flat), flat)
    assert any(
        w.startswith("Apartment: items 8, 10, 20, 21, 22, 23, 26, 30, 31 and 58 are 0.")
        and "still include roof and plinth terms" in w
        for w in warnings
    )


def test_apartment_rule_through_the_calculator():
    plan = two_storey_plan()
    plan["building_type"] = "apartment"
    result = map_plan_to_materials(plan)
    rows = {r["serial_no"]: r for r in result["items"]}
    for serial in APARTMENT_ZERO_ITEMS:
        assert rows[serial]["quantity"] == 0 and "apartment" in rows[serial]["note"]
    assert rows[9]["quantity"] > 0 and rows[11]["quantity"] > 0
    assert any(w.startswith("Apartment:") for w in result["warnings"])


# ------------------------------------------------------------------ drawn plans


def rect(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def room(room_id: str, name: str, x0: float, y0: float, x1: float, y1: float, **extra) -> dict:
    return {"id": room_id, "name": name, "polygon": rect(x0, y0, x1, y1), **extra}


def level(rooms: list[dict], openings: list[dict] | None = None, **extra) -> dict:
    return {
        "rooms": rooms,
        "openings": openings or [],
        "wall_height": 3.35,
        "wall_height_source": "stated",
        **extra,
    }


def opening(kind: str, **extra) -> dict:
    return {"id": f"{kind}-{len(extra)}", "wall_id": "w", "type": kind, **extra}


def two_storey_plan() -> dict:
    """Ground floor 10 x 8, first floor 6 x 5 over one corner."""
    ground = level(
        [
            room("g1", "Living Room", 0, 0, 6, 5),
            room("g2", "Kitchen", 6, 0, 10, 5),
            room("g3", "Bedroom 1", 0, 5, 5, 8),
            room("g4", "Bathroom", 5, 5, 7, 8),
            room("g5", "Corridor", 7, 5, 10, 8),
        ],
        [opening("door", width=0.9, height=2.1)] * 5
        + [opening("window", width=1.2, height=1.2)] * 4,
    )
    first = level(
        [
            room("f1", "Master Bedroom", 0, 0, 4, 5),
            room("f2", "Toilet", 4, 0, 6, 2.5),
            room("f3", "Study", 4, 2.5, 6, 5),
        ],
        [opening("door", width=0.9, height=2.1)] * 3
        + [opening("window", width=1.2, height=1.2)] * 2,
        elevation=3.35,
    )
    return {"units": "m", "building_type": "villa", "levels": [ground, first]}


def derived(plan: dict, **kwargs) -> dict:
    return map_plan_to_materials(plan, **kwargs)["derived_quantities"]


def quantities(result: dict) -> dict:
    return {r["serial_no"]: r["quantity"] for r in result["items"]}


# ------------------------------------------------------------------ section 7 edge cases


@pytest.mark.parametrize(
    "plan",
    [
        {"levels": [{}]},
        {"levels": [{"rooms": [], "openings": [], "walls": []}, {"rooms": []}]},
        {"levels": [level([{"id": "z", "name": "Bedroom", "polygon": [[1, 1], [1, 1], [1, 1]]}])]},
    ],
    ids=["empty level", "two empty levels", "zero-area room"],
)
def test_empty_level_or_zero_areas_give_zero_for_every_item(plan):
    result = map_plan_to_materials(plan)
    assert len(result["items"]) == 64
    assert all(r["quantity"] == 0 for r in result["items"]), [
        r["serial_no"] for r in result["items"] if r["quantity"]
    ]
    assert all(m["quantity"] == 0 for m in result["materials"])
    assert result["warnings"][-1] == (
        "No built area was found in the plan, so building quantities are zero."
    )
    assert result["derived_quantities"]["s_gyp"] == 0  # the one guarded division


def test_empty_facts_on_the_formula_layer():
    facts = PlanFacts(levels=(), rooms=(), openings=(), a_netwall=0.0, a_netwall_0=0.0)
    p = derive_primitives(facts)
    assert (p.s_gyp, p.s_cem, p.a_roof, p.p_ext_0) == (0.0, 1.0, 0.0, 0.0)
    assert all(item.quantity == 0 for item in compute_items(p, facts).values())


def test_single_room_without_openings():
    plan = {"levels": [level([room("r", "Hall", 0, 0, 5, 4)])]}
    result = map_plan_to_materials(plan)
    d = result["derived_quantities"]
    net_wall = 18 * c.SHARED_WALL_REDUCTION_FACTOR * 3.35
    assert d["A_netwall"] == pytest.approx(net_wall, abs=1e-4)
    assert d["G_ext"] == pytest.approx(18 * 3.35)  # more than the net wall area
    assert d["A_ext"] == pytest.approx(net_wall, abs=1e-4) and d["A_int"] == 0
    q = quantities(result)
    plumbing = [45, 46, "47a", 48, 49, 50, 51, 52, "53a", 54, 55, 56, "57a", "57b"]
    assert all(q[serial] == 0 for serial in plumbing)
    assert q[1] > 0 and q[7] > 0 and q["47b"] == 2 and q["53b"] == 2
    assert any(w.startswith("No bathroom or kitchen was detected") for w in result["warnings"])
    assert any("capped by the net wall area" in w for w in result["warnings"])


def test_unlabelled_rooms_are_other_and_wet_items_are_zero():
    plan = {
        "levels": [
            level(
                [
                    room("a", "Room 1", 0, 0, 4, 4),
                    room("b", "Room 2", 4, 0, 8, 4),
                    room("c", "", 0, 4, 8, 7),
                ]
            )
        ]
    }
    result = map_plan_to_materials(plan)
    assert [r["boq_type"] for r in result["room_breakdown"]] == ["OTHER", "OTHER", "OTHER"]
    d = result["derived_quantities"]
    assert (d["A_wet"], d["T_wall"], d["N_bath"], d["N_kit"]) == (0, 0, 0, 0)
    q = quantities(result)
    assert q[12] == 0 and q["18a"] == 0 and q[37] == 0 and q[55] == 0
    assert q[33] > 0 and q[36] > 0  # the rooms still get sockets and lights
    assert any(w.startswith("No bathroom or kitchen was detected") for w in result["warnings"])
    assert any(
        w.startswith("100% of the indoor area has no recognised") for w in result["warnings"]
    )


def test_arabic_and_abbreviated_labels_use_the_type_the_model_supplied():
    raw = {
        "units": "m",
        "levels": [
            {
                "name": "Ground Floor",
                "rooms": [
                    # the keyword rules return OTHER for all three names
                    room("k", "KIT.", 0, 0, 3, 4, kind="indoor", boq_type="KITCHEN"),
                    room("b", "حمام", 3, 0, 5, 4, kind="indoor", boq_type="BATH"),
                    room("d", "DRG./DN.", 0, 4, 5, 9, kind="indoor", boq_type="LIVING"),
                    # a rule matches here, so the model's answer is ignored
                    room("m", "Master Bedroom", 5, 0, 9, 9, kind="indoor", boq_type="KITCHEN"),
                ],
            }
        ],
    }
    plan = normalise_plan(raw)
    types = {r["name"]: r["boq_type"] for r in plan["levels"][0]["rooms"]}
    assert types == {
        "KIT.": "KITCHEN",
        "حمام": "BATH",
        "DRG./DN.": "LIVING",
        "Master Bedroom": "BED",
    }
    d = derived(plan)
    assert (d["N_kit"], d["N_bath"], d["N_liv"], d["N_bed"]) == (1, 1, 1, 1)
    assert d["A_kit"] == 12 and d["A_bath"] == 8


def test_upper_floor_smaller_than_ground():
    result = map_plan_to_materials(two_storey_plan())
    d = result["derived_quantities"]
    assert (d["L"], d["roof_level"]) == (2, 0)  # the roof is the largest level
    assert (d["A_roof"], d["P_roof"], d["d_roof"]) == (80, 36, 8)
    assert d["P_ext"] == [36, 22]
    assert d["G_ext"] == pytest.approx(36 * 3.35 + 22 * 3.35)  # summed per level
    assert d["A_parapet"] == 36 and d["A_ground"] == 80 and d["A_built"] == 110
    # the top level carries the parapet, the ground level the plinth
    ground, first = result["level_summaries"]
    assert (ground["parapet_wall_area_m2"], first["parapet_wall_area_m2"]) == (0.0, 36.0)
    assert ground["plinth_wall_area_m2"] > 0 and first["plinth_wall_area_m2"] == 0.0
    assert quantities(result)[34] == 3  # one board per level plus the main board


def test_roof_level_ties_go_to_the_lowest_level():
    plan = {
        "levels": [
            level([room("a", "Bedroom", 0, 0, 5, 4)]),
            level([room("b", "Bedroom", 0, 0, 4, 5)]),
        ]
    }
    d = derived(plan)
    assert d["roof_level"] == 0 and d["d_roof"] == 4


def test_l_shaped_footprint_has_an_exact_bounding_box_perimeter():
    plan = {
        "levels": [
            level([room("a", "Living Room", 0, 0, 10, 4), room("b", "Bedroom", 0, 4, 4, 10)])
        ]
    }
    d = derived(plan)
    outline = 10 + 4 + 6 + 6 + 4 + 10  # walking round the L
    assert d["P_ext"] == [outline] == [40]
    assert d["A_roof"] == 64 and d["d_roof"] == 10


def test_double_height_bathroom_keeps_its_tile_height():
    def plan(double: bool) -> dict:
        return {
            "levels": [
                level(
                    [
                        room("b", "Bathroom", 0, 0, 2, 3, is_double_height_void=double),
                        room("l", "Living Room", 2, 0, 8, 6, is_double_height_void=double),
                    ]
                )
            ]
        }

    low, high = derived(plan(False)), derived(plan(True))
    assert high["A_netwall"] == pytest.approx(2 * low["A_netwall"])  # walls are twice as tall
    assert high["T_wall"] == low["T_wall"] == pytest.approx(2.07 * 10)  # tiles stop at 2.40 m
    low_q, high_q = (quantities(map_plan_to_materials(plan(d))) for d in (False, True))
    assert high_q[12] == low_q[12] and high_q[1] > low_q[1]


def test_open_kitchen_is_a_room_and_open_labels_are_voids():
    plan = {
        "levels": [
            level(
                [
                    room("k", "Open Kitchen", 0, 0, 4, 3),
                    room("s", "OPEN TO SKY", 4, 0, 6, 3),
                    room("d", "Open Shaft", 6, 0, 7, 3),
                    room("o", "OPEN", 7, 0, 9, 3),
                    room("b", "Bedroom", 0, 3, 4, 7),
                ]
            )
        ]
    }
    result = map_plan_to_materials(plan)
    rooms = {r["id"]: r for r in result["room_breakdown"]}
    assert (rooms["k"]["kind"], rooms["k"]["boq_type"]) == ("indoor", "KITCHEN")
    for void in ("s", "d", "o"):
        assert rooms[void]["kind"] == "void" and rooms[void]["boq_type"] is None
        assert rooms[void]["included_in_built_area"] is False
    d = result["derived_quantities"]
    assert (d["A_built"], d["N_kit"], d["A_kit"]) == (28, 1, 12)
    assert d["P_ext"] == [2 * (4 + 7)]  # voids are outside the built outline
    assert d["P_site"] == 2 * (9 + 7)  # the site outline takes every room


def test_open_plan_living_dining_kitchen_counts_one_kitchen():
    plan = {
        "levels": [
            level(
                [
                    room("o", "Living / Dining / Kitchen", 0, 0, 6, 6),
                    room("b", "Bedroom", 6, 0, 10, 4),
                    room("t", "Toilet", 6, 4, 8, 6),
                ]
            )
        ]
    }
    result = map_plan_to_materials(plan)
    assert result["room_breakdown"][0]["boq_type"] == "LIVING"
    d = result["derived_quantities"]
    assert (d["N_liv"], d["N_kit"], d["open_plan_kitchens"]) == (1, 1, 1)
    assert d["A_kit"] == 12  # min(12, 36 / 3)
    assert d["P_kit"] == pytest.approx(4 * math.sqrt(12), abs=1e-4)
    assert d["A_wet"] == 12 + 4 and d["A_dry"] == 36 + 16 + 4 - 16
    assert d["N_wh"] == 2  # the bathroom and the counted kitchen
    rows = {r["serial_no"]: r for r in result["items"]}
    sockets = {part["label"]: part["quantity"] for part in rows[33]["components"]}
    # living max(2, ceil(24/4)) = 6, plus 6 for its kitchen; bedroom ceil(16/4) = 4; toilet 1
    assert sockets["13 A twin sockets"] == 6 + 6 + 4 + 1
    assert sockets["Light switches"] == 2 + 1 + 1  # the 36 m2 room gets a second switch
    assert sockets["Heater and cooker switches"] == 2 + 1
    # for every other formula it is a living room with its full area: ceil(36 / 3) spotlights
    assert rows[36]["quantity"] == 12 + ceil(16 / 3)
    assert rows[37]["quantity"] == 2 and rows[48]["quantity"] == 2

    small = {"levels": [level([room("o", "Family Hall and Kitchen", 0, 0, 5, 6)])]}
    assert derived(small)["A_kit"] == 10  # 30 / 3


def test_old_plan_without_boq_type_or_opening_sizes_still_calculates():
    plan = {
        "version": 1,
        "units": "m",
        "levels": [
            {
                "wall_height": 3.0,
                "rooms": [
                    room("r1", "Bedroom", 0, 0, 4, 4),
                    room("r2", "Kitchen", 4, 0, 7, 4),
                    room("r3", "Bath", 7, 0, 9, 4),
                    room("r4", "Living Room", 0, 4, 9, 9),
                ],
                "openings": [
                    {"id": "o1", "wall_id": "w1", "type": "door"},
                    {"id": "o2", "wall_id": "w1", "type": "door", "offset": 1.0},
                    {"id": "o3", "wall_id": "w2", "type": "window"},
                ],
            }
        ],
    }
    result = map_plan_to_materials(plan)
    assert [r["boq_type"] for r in result["room_breakdown"]] == ["BED", "KITCHEN", "BATH", "LIVING"]
    d = result["derived_quantities"]
    assert (d["N_door"], d["N_win"], d["N_bath"], d["N_kit"]) == (2, 1, 1, 1)
    q = quantities(result)
    assert len(q) == 64 and q[1] > 0 and q[55] == 1
    # one window of the default 1.20 m width; thresholds for bath, kitchen and entrance
    assert q[15] == pytest.approx((0.9 * 3 + 1.3) * 1.05)
    assert q[28] == 0 and q[29] == 0
    assert "Opening widths are absent, so items 28 and 29 are 0." in result["warnings"]


def test_same_input_twice_gives_identical_output():
    plan = two_storey_plan()
    first = json.dumps(map_plan_to_materials(plan), sort_keys=True)
    second = json.dumps(map_plan_to_materials(json.loads(json.dumps(plan))), sort_keys=True)
    assert first == second


# ------------------------------------------------------------------ boq_kind (section 2.1)

PARKING_WARNING = (
    "Parking under an upper floor is counted as paved outdoor area, so slab quantities exclude it: "
)


def ground_with_parking() -> dict:
    return level(
        [
            room("g1", "Living Room", 0, 0, 6, 5, kind="indoor"),
            room("g2", "Kitchen", 6, 0, 10, 5, kind="indoor"),
            room("g3", "PARKING 18X18'6", 0, 5, 6, 8, kind="semi_open"),
            room("g4", "Bedroom", 6, 5, 10, 8, kind="indoor"),
        ]
    )


def test_parking_under_an_upper_floor_is_paved_outdoor_area_with_a_warning():
    first = level([room("f1", "Master Bedroom", 0, 0, 10, 8, kind="indoor")])
    result = map_plan_to_materials({"units": "m", "levels": [ground_with_parking(), first]})
    parking = next(r for r in result["room_breakdown"] if r["id"] == "g3")
    # `kind` is the 3D adapter's and is reported as it was; the BOQ counts by `boq_kind`
    assert (parking["kind"], parking["boq_kind"], parking["boq_type"]) == (
        "semi_open",
        "outdoor",
        None,
    )
    assert parking["included_in_built_area"] is False
    assert parking["materials_by_key"]["tiles"]["quantity"] == 0
    d = result["derived_quantities"]
    assert (d["A_ground"], d["A_built"]) == (62, 142)  # 80 - 18 on the ground, 80 above
    assert (d["A_pave"], d["P_pave"]) == (18, 18)
    q = quantities(result)
    assert q[22] == pytest.approx(18 * 1.05)
    assert q[23] == pytest.approx(0.75 * 18 * 1.05)
    assert PARKING_WARNING + "PARKING 18X18'6." in result["warnings"]
    assert not any("items 22 and 23 are 0" in w for w in result["warnings"])


def test_parking_with_no_floor_over_it_has_no_warning():
    single = map_plan_to_materials({"units": "m", "levels": [ground_with_parking()]})
    assert single["derived_quantities"]["A_pave"] == 18
    assert not any(w.startswith(PARKING_WARNING) for w in single["warnings"])

    # an upper floor that does not reach over the parking (x from 6 to 10 only)
    beside = level([room("f1", "Master Bedroom", 6, 0, 10, 8, kind="indoor")])
    result = map_plan_to_materials({"units": "m", "levels": [ground_with_parking(), beside]})
    assert not any(w.startswith(PARKING_WARNING) for w in result["warnings"])


def test_bounding_boxes_use_boq_kind():
    plan = {
        "units": "m",
        "levels": [
            level(
                [
                    room("a", "Living Room", 0, 0, 10, 5, kind="indoor"),
                    room("b", "Car Porch", 10, 0, 15, 5, kind="semi_open"),
                ]
            )
        ],
    }
    d = derived(plan)
    assert d["P_ext"] == [30]  # the built outline stops at the living room
    assert d["P_site"] == 40  # the site outline takes every room
    assert (d["A_built"], d["A_roof"], d["A_pave"]) == (50, 50, 25)


def test_semi_open_wet_rooms_are_indoor_for_the_boq_and_stairs_stay_semi_open():
    plan = {
        "units": "m",
        "levels": [
            level(
                [
                    room("a", "Bedroom", 0, 0, 4, 4, kind="indoor"),
                    room("b", "WASH 5' WD.", 4, 0, 6, 2, kind="semi_open"),
                    room("c", "Washroom", 4, 2, 6, 4, kind="semi_open"),
                    room("d", "STAIRCASE", 0, 4, 3, 7, kind="semi_open"),
                    room("e", "Kitchen", 3, 4, 6, 7, kind="indoor"),
                ]
            )
        ],
    }
    result = map_plan_to_materials(plan)
    rooms = {r["id"]: (r["kind"], r["boq_kind"], r["boq_type"]) for r in result["room_breakdown"]}
    assert rooms["b"] == ("semi_open", "indoor", "LAUNDRY")
    assert rooms["c"] == ("semi_open", "indoor", "BATH")
    assert rooms["d"] == ("semi_open", "semi_open", None)
    d = result["derived_quantities"]
    assert (d["N_lau"], d["N_bath"], d["N_kit"]) == (1, 1, 1)
    assert (d["A_in"], d["A_built"]) == (33, 42)  # the staircase is built but not indoor
    q = quantities(result)
    assert q[27] == 2  # wet-area doors: the washroom and the wash yard


def test_a_stored_boq_kind_is_used_and_a_missing_one_is_derived():
    def a_built(**extra) -> float:
        rooms = [
            room("a", "Bedroom", 0, 0, 4, 4, kind="indoor"),
            room("p", "Parking", 4, 0, 8, 4, kind="semi_open", **extra),
        ]
        return derived({"units": "m", "levels": [level(rooms)]})["A_built"]

    assert a_built() == 16  # derived: parking is outdoor
    assert a_built(boq_kind="semi_open") == 32  # stored: kept as it is
    assert a_built(boq_kind="nonsense") == 16


def test_covered_parking_warning_on_the_formula_layer():
    facts = fixture_facts(covered_parking=("Parking 1", "Driveway"))
    warnings = calculation_warnings(derive_primitives(facts), facts)
    assert PARKING_WARNING + "Parking 1, Driveway." in warnings


# ------------------------------------------------------------------ scopes and units


def test_room_and_level_values_add_up_to_the_project_totals():
    result = map_plan_to_materials(two_storey_plan())
    project = result["materials_by_key"]
    levels = result["level_summaries"]
    rooms = [r for r in result["room_breakdown"] if r["included_in_built_area"]]

    measures = [
        ("aac_blocks", "total_masonry_area_m2"),
        ("steel_rebar", "total_steel_kg"),
        ("sand", "volume_m3"),
        ("ballast_gitti", "volume_m3"),
        ("plaster", "internal_gypsum_wall_area_m2"),
        ("plaster", "external_wet_cement_plaster_area_m2"),
        ("tiles", "total_tiled_area_with_waste_m2"),
    ]
    for key, detail in measures:
        total = project[key]["details"][detail]
        by_level = sum(s["materials_by_key"][key]["details"][detail] for s in levels)
        by_room = sum(r["materials_by_key"][key]["details"][detail] for r in rooms)
        # each scope rounds what it reports, so allow that much
        assert by_level == pytest.approx(total, abs=0.011 * len(levels)), (key, detail)
        assert by_room == pytest.approx(total, abs=0.06 * len(rooms)), (key, detail)

    # whole units round up in every scope, so the parts add up to the total or a few more
    for key in ("aac_blocks", "cement", "plaster", "tiles"):
        total = project[key]["quantity"]
        by_level = sum(s["materials_by_key"][key]["quantity"] for s in levels)
        by_room = sum(r["materials_by_key"][key]["quantity"] for r in rooms)
        assert total <= by_level <= total + len(levels), key
        assert total <= by_room <= total + len(rooms), key

    # the same wall model in every scope
    d = result["derived_quantities"]
    assert project["plaster"]["details"]["internal_gypsum_wall_area_m2"] == pytest.approx(
        d["A_gyp_wall"], abs=0.01
    )
    assert project["plaster"]["details"]["external_wet_cement_plaster_area_m2"] == pytest.approx(
        d["A_cem"], abs=0.01
    )


def test_breakdowns_keep_only_the_seven_core_materials():
    result = map_plan_to_materials(two_storey_plan())
    for scope in result["level_summaries"] + result["room_breakdown"]:
        assert list(scope["materials_by_key"]) == list(result["materials_by_key"])
        assert "items" not in scope


def test_core_rows_equal_the_scope_engine_for_a_drawn_plan():
    result = map_plan_to_materials(
        two_storey_plan(), tile_pattern="herringbone", tile_size_mm="800x800"
    )
    rows = {r["item_code"]: r for r in result["items"]}
    mats = result["materials_by_key"]
    assert rows["aac_blocks"]["quantity"] == mats["aac_blocks"]["quantity"]
    assert rows["cement"]["quantity"] == mats["cement"]["quantity"]
    assert rows["plaster"]["quantity"] == mats["plaster"]["quantity"]
    assert rows["steel_rebar"]["quantity"] == pytest.approx(
        mats["steel_rebar"]["details"]["total_steel_kg"], abs=0.05
    )
    assert rows["sand"]["quantity"] == pytest.approx(mats["sand"]["secondary_quantity"], abs=0.005)
    assert rows["ballast_gitti"]["quantity"] == pytest.approx(
        mats["ballast_gitti"]["secondary_quantity"], abs=0.005
    )
    assert rows["tiles"]["quantity"] == pytest.approx(
        mats["tiles"]["secondary_quantity"], abs=0.005
    )
    assert rows["tiles"]["components"][0]["quantity"] == mats["tiles"]["quantity"]
    assert rows["tiles"]["components"][0]["label"] == "Tiles 800 x 800 mm"


def test_unit_scale_is_applied_before_anything_is_measured():
    metres = two_storey_plan()
    feet = json.loads(json.dumps(metres))
    feet["units"] = "ft"
    for lvl in feet["levels"]:
        for r in lvl["rooms"]:
            r["polygon"] = [[x / 0.3048, y / 0.3048] for x, y in r["polygon"]]
        for o in lvl["openings"]:
            o["width"] /= 0.3048
            o["height"] /= 0.3048
    a, b = map_plan_to_materials(metres), map_plan_to_materials(feet)
    for row_m, row_ft in zip(a["items"], b["items"], strict=True):
        assert row_ft["quantity"] == pytest.approx(row_m["quantity"], abs=1e-6), row_m["serial_no"]
    assert b["derived_quantities"]["P_ext"] == pytest.approx([36, 22])


def test_calculator_inputs_false_ceiling_share_and_plot_perimeter():
    plan = two_storey_plan()
    base = quantities(map_plan_to_materials(plan))
    changed = quantities(map_plan_to_materials(plan, false_ceiling_share=0.25, plot_perimeter_m=90))
    assert changed["18b"] == pytest.approx(base["18b"] * 0.25)
    assert changed[58] == 90
    assert base[58] == pytest.approx((36 + 24) * 1.05)  # P_ext_0 + 24 beats P_site here
    assert {s for s in base if base[s] != changed[s]} == {"18b", 58}


def test_a_level_with_walls_but_no_rooms_uses_the_wall_outline():
    walls = [
        {"id": "n", "start": [0, 0], "end": [8, 0]},
        {"id": "e", "start": [8, 0], "end": [8, 6]},
        {"id": "s", "start": [8, 6], "end": [0, 6]},
        {"id": "w", "start": [0, 6], "end": [0, 0]},
    ]
    result = map_plan_to_materials({"levels": [level([], walls=walls)]})
    d = result["derived_quantities"]
    assert (d["A_built"], d["P_ext"], d["P_site"]) == (48, [28], 0)
    assert d["T_floor"] == 48  # no rooms, so no skirting
    assert any("estimated from the wall outline" in w for w in result["warnings"])
    assert quantities(result)[58] == pytest.approx((28 + 24) * 1.05)


# ------------------------------------------------------------------ frontend contract

# The bill the frontend tests render. It is written by this file, never by hand:
#   BOQ_WRITE_FIXTURE=1 uv --directory backend run pytest tests/unit/test_boq_formulas.py
FRONTEND_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "src"
    / "features"
    / "sheets"
    / "boqFullBill.fixture.json"
)


def full_bill_result() -> dict:
    """The section 8 fixture as a BOQ result, in the shape the API returns."""
    facts = fixture_facts()
    p = derive_primitives(facts)
    return {
        "items": build_boq_rows(compute_items(p, facts)),
        "warnings": calculation_warnings(p, facts),
        "geometry_summary": {
            "a_built_total_m2": round(p.a_built, 2),
            "a_built_total_sqft": round(p.a_built * 10.7639, 2),
            "levels_count": p.L,
            "rooms_count": len(facts.rooms),
            "bathrooms_count": p.n_bath,
            "kitchens_count": p.n_kit,
            "bedrooms_count": p.n_bed,
            "total_doors": p.n_door,
            "total_windows": p.n_win,
        },
        "project_metadata": {
            "project_title": "Spec fixture villa",
            "client": "NA",
            "subject": "NA",
            "building_type": facts.building_type,
            "source_file_name": "spec-fixture.pdf",
        },
    }


def test_the_frontend_fixture_is_the_bill_this_backend_produces():
    if not FRONTEND_FIXTURE.parent.is_dir():
        pytest.skip("the frontend sources are not part of this checkout")
    expected = json.dumps(full_bill_result(), indent=2, ensure_ascii=False) + "\n"
    if os.environ.get("BOQ_WRITE_FIXTURE") == "1":
        FRONTEND_FIXTURE.write_text(expected, encoding="utf-8")
    assert FRONTEND_FIXTURE.is_file(), "run once with BOQ_WRITE_FIXTURE=1 to write the fixture"
    assert FRONTEND_FIXTURE.read_text(encoding="utf-8") == expected, (
        "the BOQ rows changed: rewrite the fixture with BOQ_WRITE_FIXTURE=1 and check the "
        "frontend tests"
    )
