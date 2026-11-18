"""BOQ rows: the calculator's results in the one shape the API, the exports and the UI use.

Every row has:

    serial_no, item_code, category_code, category, sub_category, name, unit, quantity,
    quantity_decimals, components [{label, quantity, unit, quantity_decimals}],
    calc_type (geometry | count | allowance),
    quote_status (INCLUDED | EXCLUDED_FROM_QUOTE), note

`CATEGORY_PLAN` places all 59 serial numbers of the bill in their category and
sub-category. Rows exist today for the seven core materials (serials 1 to 7), built from
the calculator's `materials_by_key`. A row for one of those also keeps that material's
earlier keys (`id`, `surface_tag`, `highlight_3d`, `secondary_quantity`, `secondary_unit`,
`waste_multiplier`, `details`); `materials_by_key` itself is returned unchanged.
"""

import re
from typing import Any

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

# Units whose quantities are measured (shown with 2 decimals). Anything else is counted.
MEASURE_UNITS = frozenset(
    {
        "m",
        "rm",
        "m2",
        "m²",
        "sqm",
        "m3",
        "m³",
        "cum",
        "cft",
        "sqft",
        "kg",
        "t",
        "l",
        "litre",
        "litres",
    }
)


def category_of(serial: int) -> tuple[str, str, str]:
    """(category_code, category, sub_category) of a serial number."""
    for code, (category, subs) in CATEGORY_PLAN.items():
        for sub_category, serials in subs.items():
            if serial in serials:
                return code, category, sub_category
    raise KeyError(f"serial {serial} is not in the BOQ category plan")


def quantity_decimals(unit: str) -> int:
    """2 for a measured unit, 0 for a counted one."""
    return 2 if str(unit).strip().lower() in MEASURE_UNITS else 0


def component(label: str, quantity: Any, unit: str) -> dict[str, Any]:
    decimals = quantity_decimals(unit)
    value = float(quantity or 0.0)
    return {
        "label": label,
        "quantity": round(value, decimals) if decimals else int(round(value)),
        "unit": unit,
        "quantity_decimals": decimals,
    }


def make_row(
    serial_no: int | str,
    item_code: str,
    name: str,
    unit: str,
    quantity: Any,
    *,
    components: list[dict[str, Any]] | None = None,
    calc_type: str = "geometry",
    quote_status: str = "INCLUDED",
    note: str = "",
) -> dict[str, Any]:
    """One row in the BOQ contract. `serial_no` may carry a letter ("17a") for split rows."""
    if calc_type not in CALC_TYPES:
        raise ValueError(f"unknown calc_type {calc_type!r}")
    if quote_status not in QUOTE_STATUSES:
        raise ValueError(f"unknown quote_status {quote_status!r}")
    number = int(re.match(r"\d+", str(serial_no)).group())  # "17a" -> 17
    code, category, sub_category = category_of(number)
    decimals = quantity_decimals(unit)
    value = float(quantity or 0.0)
    return {
        "serial_no": serial_no,
        "item_code": item_code,
        "category_code": code,
        "category": category,
        "sub_category": sub_category,
        "name": name,
        "unit": unit,
        "quantity": round(value, decimals) if decimals else int(round(value)),
        "quantity_decimals": decimals,
        "components": list(components or []),
        "calc_type": calc_type,
        "quote_status": quote_status,
        "note": note,
    }


_BATHROOM = re.compile(
    r"\b(toi|toilet|toilets|bath|bathroom|w\.?\s?c|powder|lav|lavatory|washroom|restroom|shower)\b",
    re.IGNORECASE,
)


def count_bathrooms(room_name: Any) -> int:
    """1 when a room label names a toilet or bathroom ("TOI.", "BATH", "DRESS/TOI."), else 0."""
    return 1 if _BATHROOM.search(str(room_name or "")) else 0


def _waste_note(material: dict[str, Any]) -> str:
    waste = float(material.get("waste_multiplier") or 1.0) - 1.0
    return f"Includes {waste * 100:.0f}% waste." if waste > 0 else ""


# The seven core materials: serial, key in materials_by_key, unit shown, component builder.
def _core_rows(by_key: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    def details(key: str) -> dict[str, Any]:
        return (by_key.get(key) or {}).get("details") or {}

    specs: list[tuple[int, str, str, list[dict[str, Any]]]] = [
        (
            1,
            "aac_blocks",
            "nos",
            [
                component(
                    "Total masonry area", details("aac_blocks").get("total_masonry_area_m2"), "m2"
                ),
                component(
                    "Superstructure walls",
                    details("aac_blocks").get("net_superstructure_wall_m2"),
                    "m2",
                ),
                component("Plinth walls", details("aac_blocks").get("plinth_wall_area_m2"), "m2"),
                component("Parapet walls", details("aac_blocks").get("parapet_wall_area_m2"), "m2"),
                component(
                    "Clay brick equivalent",
                    details("aac_blocks").get("india_clay_bricks_equivalent"),
                    "nos",
                ),
            ],
        ),
        (
            2,
            "steel_rebar",
            "t",
            [
                component("Steel weight", details("steel_rebar").get("total_steel_kg"), "kg"),
                component(
                    "12 m bars (12 mm average)",
                    details("steel_rebar").get("tmt_12m_rods_12mm_avg"),
                    "nos",
                ),
                component(
                    "Plinth steel", details("steel_rebar").get("plinth_steel_kg_with_waste"), "kg"
                ),
                component(
                    "Superstructure steel",
                    details("steel_rebar").get("superstructure_steel_kg_with_waste"),
                    "kg",
                ),
            ],
        ),
        (
            3,
            "cement",
            "bags (50 kg)",
            [
                component("Concrete", details("cement").get("rcc_structural_bags"), "bags (50 kg)"),
                component(
                    "Block mortar", details("cement").get("block_mortar_bags"), "bags (50 kg)"
                ),
                component(
                    "Cement plaster",
                    details("cement").get("external_wet_plaster_bags"),
                    "bags (50 kg)",
                ),
                component("Total weight", details("cement").get("total_weight_kg"), "kg"),
            ],
        ),
        (
            4,
            "sand",
            "t",
            [
                component("Volume", details("sand").get("volume_m3"), "m3"),
                component("Concrete", details("sand").get("rcc_sand_m3"), "m3"),
                component("Block mortar", details("sand").get("mortar_sand_m3"), "m3"),
                component("Cement plaster", details("sand").get("external_plaster_sand_m3"), "m3"),
                component("Floor screed", details("sand").get("floor_screed_sand_m3"), "m3"),
            ],
        ),
        (
            5,
            "ballast_gitti",
            "t",
            [component("Volume", details("ballast_gitti").get("volume_m3"), "m3")],
        ),
        (
            6,
            "plaster",
            "bags (30 kg)",
            [
                component(
                    "Gypsum plaster area", details("plaster").get("internal_gypsum_area_m2"), "m2"
                ),
                component(
                    "Gypsum weight", details("plaster").get("internal_gypsum_weight_kg"), "kg"
                ),
                component(
                    "Cement plaster area",
                    details("plaster").get("external_wet_cement_plaster_area_m2"),
                    "m2",
                ),
            ],
        ),
        (
            7,
            "tiles",
            "nos",
            [
                component(
                    "Tiled area incl. waste",
                    details("tiles").get("total_tiled_area_with_waste_m2"),
                    "m2",
                ),
                component("Floor area", details("tiles").get("net_floor_area_m2"), "m2"),
                component("Skirting area", details("tiles").get("skirting_area_m2"), "m2"),
            ],
        ),
    ]
    rows: list[dict[str, Any]] = []
    for serial, key, unit, parts in specs:
        material = by_key.get(key)
        if not material:
            continue
        row = make_row(
            serial,
            key,
            str(material.get("name") or key),
            unit,
            material.get("quantity"),
            components=[p for p in parts if p["quantity"]],
            calc_type="geometry",
            quote_status="INCLUDED",
            note=_waste_note(material),
        )
        for kept in (
            "id",
            "surface_tag",
            "highlight_3d",
            "secondary_quantity",
            "secondary_unit",
            "waste_multiplier",
            "details",
        ):
            if kept in material:
                row[kept] = material[kept]
        rows.append(row)
    return rows


def serial_sort_key(serial_no: Any) -> tuple[int, str]:
    """Natural order of serial numbers: 17 < 17a < 17b < 18."""
    match = re.match(r"(\d+)(.*)", str(serial_no))
    return (int(match.group(1)), match.group(2)) if match else (10**9, str(serial_no))


def build_boq_rows(materials_by_key: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Every BOQ row the calculator can produce, in serial order."""
    return sorted(_core_rows(materials_by_key), key=lambda r: serial_sort_key(r["serial_no"]))
