"""Unit conversion. Geometry is stored in integer cm; convert only at the edges."""

from typing import Literal

DisplayUnit = Literal["cm", "m", "ft"]
InputUnit = Literal["ft", "m"]

CM_PER_FT = 30.48
CM_PER_M = 100.0


def to_cm(value: float, unit: InputUnit) -> int:
    """Convert a user length (ft or m) to whole cm."""
    factor = CM_PER_FT if unit == "ft" else CM_PER_M
    return int(round(value * factor))


def ft_in(cm: float) -> str:
    """Format cm as feet and inches, for example 400 -> 13'1\"."""
    total_in = int(round(cm / 2.54))
    feet, inches = divmod(total_in, 12)
    return f"{feet}'{inches}\"" if inches else f"{feet}'"


def fmt_length(cm: float, unit: DisplayUnit) -> str:
    if unit == "ft":
        return ft_in(cm)
    if unit == "m":
        return f"{cm / 100:.2f}"
    return f"{int(round(cm))}"


def fmt_size(w_cm: float, h_cm: float, unit: DisplayUnit) -> str:
    """Room size label, for example 400X500 (cm), 4.00X5.00 (m), 13'1\"X16'5\" (ft)."""
    return f"{fmt_length(w_cm, unit)}X{fmt_length(h_cm, unit)}"


def fmt_area(area_m2: float, unit: DisplayUnit) -> str:
    if unit == "ft":
        return f"{area_m2 * 10.7639:,.0f} SQ.FT"
    return f"{area_m2:,.1f} M2"
