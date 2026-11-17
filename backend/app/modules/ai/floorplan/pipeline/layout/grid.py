"""Planning grid shared by templates and the solver.

The plot is divided into whole grid units of about GRID_CM per axis. Converting
unit -> cm is a fixed monotone function, so rooms that share a unit edge share an
exact cm edge, and the last unit lands exactly on the plot edge even when the plot
size is not a multiple of the grid (for example 36'6" = 1113 cm).
"""

from dataclasses import dataclass

GRID_CM = 15  # one grid for templates and solver, so locked rooms always line up


@dataclass(frozen=True)
class Grid:
    width_cm: int
    depth_cm: int
    nx: int
    ny: int

    @classmethod
    def for_plot(cls, width_cm: int, depth_cm: int, step: int = GRID_CM) -> "Grid":
        return cls(
            width_cm, depth_cm, max(1, round(width_cm / step)), max(1, round(depth_cm / step))
        )

    @property
    def gx(self) -> float:
        return self.width_cm / self.nx

    @property
    def gy(self) -> float:
        return self.depth_cm / self.ny

    def x_cm(self, u: int) -> int:
        return round(u * self.width_cm / self.nx)

    def y_cm(self, u: int) -> int:
        return round(u * self.depth_cm / self.ny)

    def x_units(self, cm: float) -> int:
        return max(0, min(self.nx, round(cm * self.nx / self.width_cm)))

    def y_units(self, cm: float) -> int:
        return max(0, min(self.ny, round(cm * self.ny / self.depth_cm)))

    def snap_x(self, cm: float) -> int:
        return self.x_cm(self.x_units(cm))

    def snap_y(self, cm: float) -> int:
        return self.y_cm(self.y_units(cm))
