"""Quantities: pure functions, every number in the report comes from here.

    net    = surface area x coverage share
    total  = net x (1 + wastage %)              rounded half-up to 0.1 sq ft
    buy    = total / unit size, rounded UP      (sheets, boxes, rolls, litres)

Worked example (TV wall 12 x 10 ft, fluted veneer 70 %, marble 30 %, wastage 10 %):
    veneer 120 x 0.7 = 84 -> 92.4 sq ft -> 92.4 / 32 = 2.9 -> 3 sheets (8 x 4 ft)
    marble 120 x 0.3 = 36 -> 39.6 sq ft
"""

import math
from dataclasses import dataclass, field

from app.modules.ai.material_agent.data_files import catalog_by_id, rules
from app.modules.ai.material_agent.geometry import AppArea, NeedsInput, application_area
from app.modules.ai.material_agent.schemas import (
    ApplicationRequest,
    BreakdownLine,
    Material,
    MaterialReport,
    Overrides,
    PieceSize,
    QuantityLine,
    TargetSpace,
)
from app.modules.ai.material_agent.units import fmt, round_half_up

QTY_BASES_WITH_AREA = ("area",)


def wastage_for(material: Material, override: float | None = None) -> tuple[float, str]:
    """(percent, why) from the override, the laying pattern, or the catalog group."""
    r = rules()
    if override is not None:
        return float(override), "set by you"
    pattern = f"{material.pattern} {material.name}".lower()
    for key, pct in r.get("pattern_wastage_pct", {}).items():
        if not key.startswith("_") and key in pattern:
            return float(pct), f"{key} pattern"
    entry = catalog_by_id().get(material.catalog_id or "")
    group = entry["wastage_group"] if entry else "default"
    table = r["wastage_pct"]
    return float(table.get(group, table["default"])), f"standard for {group.replace('_', ' ')}"


def _plural(n: float, one: str, many: str | None = None) -> str:
    return one if n == 1 else (many or one + "s")


def _ceil(x: float) -> int:
    return math.ceil(round(x, 6))


def buy_units(
    material: Material, total_sqft: float, net_sqft: float
) -> tuple[float | None, str | None, BreakdownLine | None]:
    """How many sheets / boxes / rolls / litres to buy (None when sold by area)."""
    entry = catalog_by_id().get(material.catalog_id or "")
    if not entry:
        return None, None, None
    buy = entry["buy"]
    kind = buy["kind"]
    if kind == "sheet":
        w, ln = float(buy["width_ft"]), float(buy["length_ft"])
        size = w * ln
        n = _ceil(total_sqft / size)
        unit = f"{_plural(n, 'sheet')} ({fmt(ln)} × {fmt(w)} ft)"
        return (
            n,
            unit,
            BreakdownLine(
                label="Sheets",
                formula=f"{fmt(total_sqft)} ÷ {fmt(size)} = {fmt(total_sqft / size)}, rounded up",
                value=n,
            ),
        )
    if kind == "box":
        size = float(buy["sqft_per_box"])
        n = _ceil(total_sqft / size)
        return (
            n,
            f"boxes ({buy.get('label') or fmt(size) + ' sq ft'})",
            BreakdownLine(
                label="Boxes",
                formula=f"{fmt(total_sqft)} ÷ {fmt(size, 2)} = {fmt(total_sqft / size)}, "
                "rounded up",
                value=n,
            ),
        )
    if kind == "roll":
        size = float(buy["sqft_per_roll"])
        n = _ceil(total_sqft / size)
        return (
            n,
            f"rolls ({fmt(size)} sq ft each)",
            BreakdownLine(
                label="Rolls",
                formula=f"{fmt(total_sqft)} ÷ {fmt(size)} = {fmt(total_sqft / size)}, rounded up",
                value=n,
            ),
        )
    if kind == "paint":
        p = rules()["paint"]
        coats, per = int(p["coats"]), float(p["sqft_per_litre_per_coat"])
        litres = total_sqft * coats / per
        n = _ceil(litres)
        return (
            n,
            f"litres ({coats} coats)",
            BreakdownLine(
                label="Paint",
                formula=f"{fmt(total_sqft)} × {coats} coats ÷ {fmt(per)} sq ft per litre = "
                f"{fmt(litres)}, rounded up",
                value=n,
            ),
        )
    return None, None, None


def quantity_line(
    material: Material,
    area: AppArea,
    coverage: float,
    *,
    wastage_override: float | None = None,
    piece: PieceSize | None = None,
) -> QuantityLine:
    coverage = min(max(coverage, 0.0), 1.0)
    net = area.area_sqft * coverage
    wastage, why = wastage_for(material, wastage_override)
    total = round_half_up(net * (1 + wastage / 100), 1)
    net_r = round_half_up(net, 1)
    lines = list(area.breakdown)
    if len(area.breakdown) > 1:
        lines.append(
            BreakdownLine(
                label="Surface area",
                formula="sum of the lines above",
                value=round_half_up(area.area_sqft, 2),
            )
        )
    if coverage < 1:
        lines.append(
            BreakdownLine(
                label=f"{material.display_name} share",
                formula=f"{fmt(area.area_sqft)} × {fmt(coverage * 100)}%",
                value=net_r,
            )
        )
    lines.append(
        BreakdownLine(
            label=f"Wastage {fmt(wastage)}% ({why})",
            formula=f"{fmt(net)} × {fmt(1 + wastage / 100, 3)}",
            value=total,
        )
    )
    if piece is not None:  # the size the person will buy ("2 x 4 ft tiles")
        size = piece.width_ft * piece.length_ft
        n = _ceil(total / size)
        buy_qty, buy_unit = n, f"{_plural(n, 'piece')} ({piece.label})"
        buy_line = BreakdownLine(
            label="Pieces",
            formula=f"{fmt(total)} ÷ {fmt(size, 2)} sq ft per piece = {fmt(total / size)}, "
            "rounded up",
            value=n,
        )
    else:
        buy_qty, buy_unit, buy_line = buy_units(material, total, net)
    if buy_line:
        lines.append(buy_line)
    return QuantityLine(
        material_id=material.id,
        material=material.display_name,
        application=area.label,
        surface_sqft=round_half_up(area.area_sqft, 1),
        coverage_ratio=round_half_up(coverage, 3),
        net_qty=net_r,
        wastage_pct=wastage,
        total_qty=total,
        unit="sq ft",
        buy_qty=buy_qty,
        buy_unit=buy_unit,
        breakdown=lines,
        assumptions=list(area.assumptions),
    )


# ------------------------------------------------------------ whole report


@dataclass
class Applied:
    """A follow-up request kept on the session so recalculation repeats it."""

    material_id: str
    request: ApplicationRequest
    target: TargetSpace
    coverage: float = 1.0


@dataclass
class ReportResult:
    report: MaterialReport
    questions: list[NeedsInput] = field(default_factory=list)


def default_application(material: Material, target: TargetSpace) -> ApplicationRequest | None:
    """Where a detected material goes on the measured space (None = identify only)."""
    match material.surface:
        case "floor":
            return ApplicationRequest(application="floor") if target.room else None
        case "ceiling":
            return ApplicationRequest(application="ceiling") if target.room else None
        case "wall":
            return ApplicationRequest(application="one_wall" if target.wall else "all_walls")
        case "facade":
            return ApplicationRequest(application="one_wall") if target.wall else None
    return None  # countertop / backsplash need a layout; furniture, doors... are identified only


def coverage_shares(
    materials: list[Material], overrides: dict[str, float]
) -> tuple[dict[str, float], list[str]]:
    """Coverage per material on one surface: given shares, scaled to 100 % at most;
    missing ones share what is left."""
    notes: list[str] = []
    given = {m.id: overrides.get(m.id, m.coverage_ratio) for m in materials}
    known = {k: float(v) for k, v in given.items() if v is not None}
    fixed = {k: v for k, v in known.items() if k in overrides}  # set by the person: kept
    photo = {k: v for k, v in known.items() if k not in overrides}
    if fixed and sum(fixed.values()) + sum(photo.values()) > 1.0001:
        room = max(1.0 - sum(fixed.values()), 0.0)
        scale = room / sum(photo.values()) if photo else 0.0
        known = {**fixed, **{k: v * scale for k, v in photo.items()}}
        notes.append("The other materials on that surface were adjusted to your share.")
    total_known = sum(known.values())
    if total_known > 1.0001:
        notes.append(
            "The coverage shares seen in the photo added up to more than 100 %; "
            "they were scaled down."
        )
        known = {k: v / total_known for k, v in known.items()}
        total_known = 1.0
    unknown = [k for k, v in given.items() if v is None]
    if unknown:
        share = max(1.0 - total_known, 0.0) / len(unknown) if (known or len(unknown) > 1) else 1.0
        for k in unknown:
            known[k] = share
        if len(materials) > 1:
            notes.append(
                "Where the photo gave no share, the rest of the surface was split equally."
            )
    return known, notes


def build_report(
    materials: list[Material],
    target: TargetSpace | None,
    applied: list[Applied],
    overrides: Overrides,
    version: int,
) -> ReportResult:
    by_id = {m.id: m for m in materials}
    report = MaterialReport(version=version, target=target)
    questions: list[NeedsInput] = []
    if target is None:
        report.identified_only = [m.id for m in materials]
        report.assumptions.append("Add the room or wall size to get quantities.")
    else:
        if target.room and overrides.ceiling_height_ft:
            target = target.model_copy(deep=True)
            assert target.room is not None
            target.room.height_ft = overrides.ceiling_height_ft
            report.target = target
        groups: dict[str, tuple[ApplicationRequest, list[Material]]] = {}
        for m in materials:
            req = default_application(m, target)
            if req is None:
                report.identified_only.append(m.id)
                continue
            groups.setdefault(req.application, (req, []))[1].append(m)
        for req, group in groups.values():
            area = application_area(target, req)
            if isinstance(area, NeedsInput):
                questions.append(area)
                report.identified_only += [m.id for m in group]
                continue
            shares, notes = coverage_shares(group, overrides.coverage_ratio)
            report.assumptions += notes
            for m in group:
                report.lines.append(
                    quantity_line(
                        m,
                        area,
                        shares[m.id],
                        wastage_override=overrides.wastage_pct.get(m.id),
                        piece=overrides.piece_size.get(m.id),
                    )
                )
    for a in applied:
        m = by_id.get(a.material_id)
        if m is None:
            continue
        tgt = a.target
        if tgt.room and overrides.ceiling_height_ft and tgt.source == "manual":
            tgt = tgt.model_copy(deep=True)
            assert tgt.room is not None
            tgt.room.height_ft = overrides.ceiling_height_ft
        area = application_area(tgt, a.request)
        if isinstance(area, NeedsInput):
            questions.append(area)
            continue
        cov = overrides.coverage_ratio.get(
            f"{m.id}@{a.request.application}", overrides.coverage_ratio.get(m.id, a.coverage)
        )
        line = quantity_line(
            m,
            area,
            cov,
            wastage_override=overrides.wastage_pct.get(m.id),
            piece=overrides.piece_size.get(m.id),
        )
        report.lines.append(line)
        if m.id in report.identified_only:
            report.identified_only.remove(m.id)
    for line in report.lines:
        for note in line.assumptions:
            if note not in report.assumptions:
                report.assumptions.append(note)
    from app.modules.ai.material_agent.tools import supporting  # tools imports this module's deps

    report.supporting = supporting(report.lines, materials)
    return ReportResult(report=report, questions=questions)
