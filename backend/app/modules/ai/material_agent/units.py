"""Length units and number formatting (feet first, as the firm works in feet)."""

from decimal import ROUND_HALF_UP, Decimal

TO_FT = {"ft": 1.0, "in": 1 / 12, "m": 1 / 0.3048, "cm": 1 / 30.48, "mm": 1 / 304.8}


def to_ft(value: float, unit: str) -> float:
    try:
        return value * TO_FT[unit]
    except KeyError as e:
        raise ValueError(f"unknown unit: {unit}") from e


def m_to_ft(value: float) -> float:
    return value / 0.3048


def round_half_up(value: float, decimals: int = 1) -> float:
    """92.40000000000001 -> 92.4 and 0.05 -> 0.1 (not banker's rounding)."""
    q = Decimal(1).scaleb(-decimals)
    return float(Decimal(repr(value)).quantize(q, rounding=ROUND_HALF_UP))


def fmt(value: float, decimals: int = 1) -> str:
    """12.0 -> '12', 92.4 -> '92.4' (no trailing .0)."""
    v = round_half_up(value, decimals)
    return f"{v:.{decimals}f}".rstrip("0").rstrip(".") if decimals else str(int(v))
