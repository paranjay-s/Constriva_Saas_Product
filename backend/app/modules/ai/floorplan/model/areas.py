"""The area statement, worded the same in the title block and in the chat.

    Total area 5,000 sq ft (3,500 sq ft built-up + 1,500 sq ft exterior)
    Total area 464.5 m² (325.2 m² built-up + 139.4 m² exterior), coverage 70%
    Built-up 3,500 sq ft gross / 3,120 sq ft net (inside the walls)

Gross built-up is measured to the outer face of the external walls (Dubai Building Code
K.5.2.7 plot coverage); net is the sum of the rooms inside their wall faces.
"""

from app.modules.ai.floorplan.model.building import Areas

SQFT_PER_M2 = 10.7639


def _sqft(m2: float) -> str:
    return f"{m2 * SQFT_PER_M2:,.0f} sq ft"


def _m2(m2: float) -> str:
    return f"{m2:,.1f} m²"


def area_lines(a: Areas, unit: str = "ft") -> list[str]:
    """Three lines: the total in the person's unit, the same in m² with coverage, and
    gross versus net. For metric plans the first line is already in m²."""
    sq = _sqft if unit == "ft" else _m2
    first = (
        f"Total area {sq(a.plot_m2)} ({sq(a.built_up_m2)} built-up + "
        f"{sq(a.exterior_m2)} exterior)"
    )
    metric = (
        f"Total area {_m2(a.plot_m2)} ({_m2(a.built_up_m2)} built-up + "
        f"{_m2(a.exterior_m2)} exterior), coverage {a.coverage:.0%}"
    )
    net = f"Built-up {sq(a.built_up_m2)} gross / {sq(a.built_up_net_m2)} net (inside the walls)"
    if unit == "ft":
        return [first, metric, net]
    return [f"{metric}", net]


def area_sentence(a: Areas, unit: str = "ft") -> str:
    return ". ".join(area_lines(a, unit)) + "."
