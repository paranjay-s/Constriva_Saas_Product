"""BOQ rows: the calculator's results in the one shape the API, the exports and the UI use.

Every row has:

    serial_no, item_code, category_code, category, sub_category, name, unit, quantity,
    quantity_decimals, components [{label, quantity, unit, quantity_decimals}],
    calc_type (geometry | count | allowance),
    quote_status (INCLUDED | EXCLUDED_FROM_QUOTE), note

`CATALOG` names every row of the bill (spec section 4): 59 items, five of them split into
two lettered rows (17a/b, 18a/b, 47a/b, 53a/b, 57a/b), 64 rows in all. `CATEGORY_PLAN`
places each serial in its category and sub-category (spec section 5).

`quantity` is the exact value of the formula. `quantity_decimals` says how to show it:
0 for counts and for quantities the formula rounds up, 2 for measures.

Rows 1 to 7 also keep the keys the seven core materials have always had (`id`,
`surface_tag`, `highlight_3d`, `secondary_quantity`, `secondary_unit`, `waste_multiplier`,
`details`); `materials_by_key` itself is returned unchanged in shape.
"""

import re
from dataclasses import dataclass
from typing import Any

from app.modules.sheets.formulas import ItemValue, Serial

CALC_TYPES = ("geometry", "count", "allowance")
QUOTE_STATUSES = ("INCLUDED", "EXCLUDED_FROM_QUOTE")

# category code -> (category, {sub-category: serial numbers})
CATEGORY_PLAN: dict[str, tuple[str, dict[str, tuple[int, ...]]]] = {
    "A": (
        "Structure and Masonry",
        {
            "Masonry": (1,),
            "Reinforcement": (2,),
            "Concrete and binders": (3,),
            "Aggregates": (4, 5),
            "Wall finishes": (6,),
            "Flooring": (7,),
        },
    ),
    "B": (
        "Civil, Finishing and Waterproofing",
        {
            "Roofing and waterproofing": (8, 9, 10, 11),
            "Tiling": (12, 13, 14),
            "Stone and feature": (15, 16),
            "Painting": (17, 19, 21),
            "Ceilings": (18,),
            "External render": (20,),
            "External works": (22, 23),
        },
    ),
    "C": (
        "Architectural Components",
        {
            "Access and metalwork": (24, 25, 26),
            "Doors and glazing": (27, 28, 29),
            "External works": (30, 31),
        },
    ),
    "D": (
        "Electrical and HVAC",
        {
            "Cabling and containment": (32, 42),
            "Wiring devices": (33,),
            "Distribution and protection": (34, 35),
            "Lighting": (36, 39, 40, 41),
            "Ventilation and controls": (37, 43),
            "Water heating": (38,),
        },
    ),
    "E": (
        "Plumbing and Sanitary",
        {
            "Drainage": (44, 53, 54, 57),
            "Valves and fittings": (45, 46, 47),
            "Sanitary fixtures": (48, 49, 50, 55, 56),
            "Pumps and storage": (51, 52),
        },
    ),
    "F": ("Site Setup", {"Preliminaries": (58, 59)}),
}

TOTAL_SERIALS = 59


@dataclass(frozen=True)
class CatalogItem:
    serial: Serial
    item_code: str
    name: str
    unit: str
    calc_type: str  # geometry | count | allowance
    decimals: int = 0  # 0: shown as a whole number; 2: shown with two decimals
    excluded: bool = False  # EXCL in the spec: computed, but left out of the quote


def _item(
    serial: Serial,
    code: str,
    name: str,
    unit: str,
    kind: str,
    decimals: int = 0,
    excluded: bool = False,
) -> CatalogItem:
    calc_type = {"G": "geometry", "C": "count", "A": "allowance"}[kind]
    return CatalogItem(serial, code, name, unit, calc_type, decimals, excluded)


# Spec section 4, in serial order. Units are written as the spec writes them.
CATALOG: tuple[CatalogItem, ...] = (
    # A: structure and masonry
    _item(1, "aac_blocks", "AAC blocks", "pieces", "G"),
    _item(2, "steel_rebar", "Steel rebar", "t", "G", 2),
    _item(3, "cement", "Cement", "50 kg bags", "G"),
    _item(4, "sand", "Sand", "m³", "G", 2),
    _item(5, "ballast_gitti", "Coarse aggregate", "m³", "G", 2),
    _item(6, "plaster", "Gypsum plaster", "30 kg bags", "G"),
    _item(7, "tiles", "Floor tiles and skirting", "m²", "G", 2),
    # B: civil, finishing and waterproofing
    _item(8, "pu_spray_foam", "PU spray foam", "m²", "G", 2),
    _item(9, "bitumen_coating", "Bitumen coating", "L", "G"),
    _item(10, "lightweight_screed", "Lightweight screed", "m³", "G", 2),
    _item(11, "waterproofing_coat", "Waterproofing coat", "kg", "G"),
    _item(12, "wet_area_wall_tiles", "Wet-area wall tiles", "m²", "G", 2),
    _item(13, "tile_grout", "Tile grout", "kg", "G"),
    _item(14, "cleaning_solvents", "Cleaning solvents", "L", "A"),
    _item(15, "marble_thresholds_sills", "Marble thresholds and sills", "LM", "C", 2),
    _item(16, "ceramic_niches", "Ceramic niches", "m²", "A", 2),
    _item("17a", "interior_wall_paint", "Interior wall paint", "L", "G"),
    _item("17b", "interior_wall_primer", "Interior wall primer", "L", "G"),
    _item("18a", "mr_gypsum_board", "MR gypsum board", "m²", "G", 2),
    _item("18b", "regular_gypsum_board", "Regular gypsum board", "m²", "G", 2),
    _item(19, "ceiling_paint", "Ceiling paint", "L", "G"),
    _item(20, "exterior_plaster", "Exterior plaster", "m²", "G", 2),
    _item(21, "exterior_paint", "Exterior paint", "L", "G"),
    _item(22, "interlock_paving", "Interlock paving", "m²", "G", 2, excluded=True),
    _item(23, "kerbstone", "Kerbstone", "LM", "G", 2, excluded=True),
    # C: architectural components
    _item(24, "ceiling_access_hatches", "Ceiling access hatches", "Nos", "C"),
    _item(25, "aluminium_canopy", "Aluminium canopy / AC screen", "Nos", "A"),
    _item(26, "steel_access_ladder", "Steel access ladder", "Nos", "C"),
    _item(27, "wet_area_doors", "Wet-area doors", "Nos", "C"),
    _item(28, "aluminium_curtain_wall", "Aluminium curtain wall", "m²", "G", 2),
    _item(29, "internal_glass_doors", "Internal glass doors", "Nos", "G"),
    _item(30, "pergola", "Pergola", "m²", "G", 2, excluded=True),
    _item(31, "gates", "Gates", "Sets", "A", excluded=True),
    # D: electrical and HVAC
    _item(32, "cable_single_core", "Cable (single core)", "LM", "G"),
    _item(33, "switches_sockets", "Switches and sockets", "Nos", "C"),
    _item(34, "distribution_boards", "Distribution boards", "Nos", "C"),
    _item(35, "breakers_isolators", "Breakers and isolators", "Nos", "C"),
    _item(36, "led_spotlights", "LED spotlights", "Nos", "G"),
    _item(37, "exhaust_fans", "Exhaust fans", "Nos", "C"),
    _item(38, "water_heaters", "Water heaters", "Nos", "C"),
    _item(39, "chandeliers", "Chandeliers", "Nos", "A"),
    _item(40, "bathroom_ip65_lights", "Bathroom IP65 lights", "Nos", "G"),
    _item(41, "led_strip", "LED strip", "LM", "A", 2),
    _item(42, "aluminium_led_channel", "Aluminium LED channel", "LM", "A", 2),
    _item(43, "thermostats", "Thermostats", "Nos", "C"),
    # E: plumbing and sanitary
    _item(44, "ac_condensate_drain", "AC condensate drain", "LM", "C", 2),
    _item(45, "angle_valves", "Angle valves", "Nos", "C"),
    _item(46, "isolation_valves", "Isolation valves", "Nos", "C"),
    _item("47a", "shattaf_sets", "Shattaf sets", "Nos", "C"),
    _item("47b", "hose_bibs", "Hose bibs", "Nos", "C"),
    _item(48, "basin_sink_mixers", "Basin and sink mixers", "Nos", "C"),
    _item(49, "shower_mixer_sets", "Shower mixer sets", "Sets", "C"),
    _item(50, "toilet_accessory_sets", "Toilet accessory sets", "Sets", "C"),
    _item(51, "pump_sets", "Pump sets", "Sets", "C"),
    _item(52, "water_tanks", "Water tanks", "Nos", "C", excluded=True),
    _item("53a", "floor_traps", "Floor traps", "Nos", "C"),
    _item("53b", "roof_rainwater_outlets", "Roof rainwater outlets", "Nos", "G"),
    _item(54, "bottle_traps", "Bottle traps", "Nos", "C"),
    _item(55, "water_closets", "Water closets", "Nos", "C"),
    _item(56, "basins_sinks", "Basins and sinks", "Nos", "C", excluded=True),
    _item("57a", "gully_traps", "Gully traps", "Nos", "C"),
    _item("57b", "inspection_manholes", "Inspection manholes", "Nos", "G"),
    # F: site setup
    _item(58, "site_hoarding", "Site hoarding", "LM", "G", 2),
    _item(59, "project_signboard", "Project signboard", "No.", "C"),
)

CATALOG_BY_SERIAL: dict[Serial, CatalogItem] = {item.serial: item for item in CATALOG}

# Keys a row of the seven core materials carries over from `materials_by_key`.
LEGACY_KEYS = (
    "id",
    "surface_tag",
    "highlight_3d",
    "secondary_quantity",
    "secondary_unit",
    "waste_multiplier",
    "details",
)


# Units shown with two decimals when a row does not say how to show its quantity.
MEASURE_UNITS = frozenset(
    {
        "m",
        "rm",
        "lm",
        "m2",
        "m²",
        "sqm",
        "sqft",
        "m3",
        "m³",
        "cum",
        "cft",
        "kg",
        "t",
        "tonne",
        "tonnes",
        "metric_tons",
        "l",
        "litre",
        "litres",
    }
)


def quantity_decimals(unit: str) -> int:
    """Decimals for a row that carries no `quantity_decimals`: 2 for a measure, 0 for a count."""
    return 2 if str(unit).strip().lower() in MEASURE_UNITS else 0


def serial_number(serial_no: Any) -> int:
    """The number of a serial: 17 for 17, "17" and "17a"."""
    match = re.match(r"\d+", str(serial_no))
    if not match:
        raise ValueError(f"not a serial number: {serial_no!r}")
    return int(match.group())


def serial_sort_key(serial_no: Any) -> tuple[int, str]:
    """Natural order of serial numbers: 17 < 17a < 17b < 18."""
    match = re.match(r"(\d+)(.*)", str(serial_no))
    return (int(match.group(1)), match.group(2)) if match else (10**9, str(serial_no))


def group_sort_key(row: dict[str, Any]) -> tuple[int, int, tuple[int, str]]:
    """Order that keeps a bill grouped: category, then sub-category, then serial number.

    Categories and sub-categories come in the order of `CATEGORY_PLAN`, so a sub-category
    whose serials are not consecutive (Painting: 17, 19, 21) still stays together. A row
    whose serial is not in the plan goes last, in serial order.
    """
    serial = serial_sort_key(row.get("serial_no"))
    for category_index, (_, subs) in enumerate(CATEGORY_PLAN.values()):
        for sub_index, serials in enumerate(subs.values()):
            if serial[0] in serials:
                return category_index, sub_index, serial
    return len(CATEGORY_PLAN), 0, serial


def category_of(serial: Any) -> tuple[str, str, str]:
    """(category_code, category, sub_category) of a serial number."""
    number = serial_number(serial)
    for code, (category, subs) in CATEGORY_PLAN.items():
        for sub_category, serials in subs.items():
            if number in serials:
                return code, category, sub_category
    raise KeyError(f"serial {serial} is not in the BOQ category plan")


def shown(value: Any, decimals: int) -> int | float:
    """A quantity as stored in a row: a whole number, or the exact value free of float noise."""
    number = float(value or 0.0)
    return int(round(number)) if decimals == 0 else round(number, 6)


def component(label: str, quantity: Any, unit: str, decimals: int | None = None) -> dict[str, Any]:
    decimals = quantity_decimals(unit) if decimals is None else decimals
    return {
        "label": label,
        "quantity": shown(quantity, decimals),
        "unit": unit,
        "quantity_decimals": decimals,
    }


def make_row(
    serial_no: Serial,
    item_code: str,
    name: str,
    unit: str,
    quantity: Any,
    *,
    decimals: int | None = None,
    components: list[dict[str, Any]] | None = None,
    calc_type: str = "geometry",
    quote_status: str = "INCLUDED",
    note: str = "",
) -> dict[str, Any]:
    """One row in the BOQ contract. `serial_no` may carry a letter ("17a") for split rows.

    `decimals` says how the quantity is shown; when it is left out the unit decides.
    """
    decimals = quantity_decimals(unit) if decimals is None else decimals
    if calc_type not in CALC_TYPES:
        raise ValueError(f"unknown calc_type {calc_type!r}")
    if quote_status not in QUOTE_STATUSES:
        raise ValueError(f"unknown quote_status {quote_status!r}")
    code, category, sub_category = category_of(serial_no)
    return {
        "serial_no": serial_no,
        "item_code": item_code,
        "category_code": code,
        "category": category,
        "sub_category": sub_category,
        "name": name,
        "unit": unit,
        "quantity": shown(quantity, decimals),
        "quantity_decimals": decimals,
        "components": list(components or []),
        "calc_type": calc_type,
        "quote_status": quote_status,
        "note": note,
    }


def build_boq_rows(
    values: dict[Serial, ItemValue],
    materials_by_key: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Every row of the bill, in serial order, from the formula results.

    `materials_by_key` supplies the earlier keys of the seven core materials.
    """
    legacy = materials_by_key or {}
    rows: list[dict[str, Any]] = []
    for item in CATALOG:
        value = values.get(item.serial)
        if value is None:
            continue
        row = make_row(
            item.serial,
            item.item_code,
            item.name,
            item.unit,
            value.quantity,
            decimals=item.decimals,
            components=[
                component(part.label, part.quantity, part.unit, part.decimals)
                for part in value.parts
            ],
            calc_type=item.calc_type,
            quote_status="EXCLUDED_FROM_QUOTE" if item.excluded else "INCLUDED",
            note=value.note,
        )
        material = legacy.get(item.item_code)
        if material:
            for key in LEGACY_KEYS:
                if key in material:
                    row[key] = material[key]
        rows.append(row)
    return sorted(rows, key=lambda r: serial_sort_key(r["serial_no"]))
