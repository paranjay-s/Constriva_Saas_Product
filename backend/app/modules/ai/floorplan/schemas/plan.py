"""FloorPlan: the single source of truth for a generated 2D plan.

Coordinate system: integer cm, origin at the plot's north-west corner, x grows east,
y grows south (north is up on the drawing). A room is an axis-aligned rectangle
measured on wall centre lines, so neighbouring rooms share an edge.

Openings are positioned on a wall of the room they belong to:
- `wall` is the side of that room (north/south/east/west),
- `offset` is measured from the wall's start: the west end of a north/south wall,
  the north end of an east/west wall.
A door sits on a wall of its `to` room; `from` is the room on the other side
(None means outside). "in" swings open into the `to` room, "out" into `from`.
Fixture x/y are the fixture's centre, relative to its room's north-west corner, so
fixtures move with their room.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.ai.floorplan.schemas.common import ZONE_BY_TYPE, RoomType, Side, is_open
from app.modules.ai.floorplan.units import DisplayUnit

SymbolName = Literal[
    "bed_double",
    "bed_single",
    "wardrobe",
    "side_table",
    "sofa_3",
    "armchair",
    "coffee_table",
    "dining_4",
    "dining_6",
    "kitchen_counter",
    "toilet",
    "basin",
    "bathtub",
    "shower",
    "desk",
    "tree",
    "plant",
]

Swing = Literal["in-left", "in-right", "out-left", "out-right", "none"]


class _Model(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class Meta(_Model):
    project: str = ""
    owner: str = ""
    floor_name: str = "GROUND FLOOR"
    unit_display: DisplayUnit = "cm"


class Setbacks(_Model):
    """Distances (cm) enclosed rooms keep from the plot edge. Front is the road side;
    left and right are as seen from the road, facing the house. Open areas (pool,
    garden, parking...) may use the setbacks; everything stays inside the plot."""

    front: int = Field(default=0, ge=0)
    rear: int = Field(default=0, ge=0)
    left: int = Field(default=0, ge=0)
    right: int = Field(default=0, ge=0)


class Plot(_Model):
    width: int = Field(gt=0, description="East-west size in cm")
    depth: int = Field(gt=0, description="North-south size in cm")
    road_side: Side | None = None
    setbacks: Setbacks = Field(default_factory=Setbacks)
    built_up_m2: float | None = Field(
        default=None, gt=0, description="Target built-up (covered) area; None = no target"
    )

    def buildable(self) -> tuple[int, int, int, int]:
        """(x0, y0, x1, y1) in cm: the plot inside the setbacks."""
        sb = self.setbacks
        n, s, w, e = {
            "south": (sb.rear, sb.front, sb.left, sb.right),
            "north": (sb.front, sb.rear, sb.right, sb.left),
            "east": (sb.left, sb.right, sb.rear, sb.front),
            "west": (sb.right, sb.left, sb.front, sb.rear),
        }[self.road_side or "south"]
        return w, n, self.width - e, self.depth - s

    @property
    def has_setbacks(self) -> bool:
        sb = self.setbacks
        return bool(sb.front or sb.rear or sb.left or sb.right)


class Room(_Model):
    id: str = Field(min_length=1)
    type: RoomType
    label: str
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(gt=0)
    h: int = Field(gt=0)
    locked: bool = False
    part_of: str | None = Field(
        default=None,
        description="Leftover space (shaft) drawn as part of this open area, e.g. the garden",
    )

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def area_m2(self) -> float:
        return self.w * self.h / 10_000

    @property
    def zone(self) -> str:
        return ZONE_BY_TYPE[self.type]

    @property
    def is_open(self) -> bool:
        return is_open(self.type)


class Door(_Model):
    id: str = Field(min_length=1)
    from_room: str | None = Field(default=None, alias="from")
    to_room: str = Field(alias="to")
    wall: Side
    offset: int = Field(ge=0)
    width: int = Field(gt=0)
    swing: Swing = "in-left"


class Window(_Model):
    id: str = Field(min_length=1)
    room: str
    wall: Side
    offset: int = Field(ge=0)
    width: int = Field(gt=0)


class Fixture(_Model):
    id: str = Field(min_length=1)
    room: str
    symbol: SymbolName
    x: int
    y: int
    rotation: Literal[0, 90, 180, 270] = 0


class FloorPlan(_Model):
    id: str = Field(min_length=1)
    meta: Meta = Field(default_factory=Meta)
    plot: Plot
    rooms: list[Room] = Field(default_factory=list)
    doors: list[Door] = Field(default_factory=list)
    windows: list[Window] = Field(default_factory=list)
    fixtures: list[Fixture] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_ids_and_references(self) -> "FloorPlan":
        ids = [r.id for r in self.rooms] + [
            o.id for o in (*self.doors, *self.windows, *self.fixtures)
        ]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate ids: {dupes}")
        room_ids = {r.id for r in self.rooms}
        bad = [d.id for d in self.doors if d.to_room not in room_ids]
        bad += [d.id for d in self.doors if d.from_room is not None and d.from_room not in room_ids]
        bad += [w.id for w in self.windows if w.room not in room_ids]
        bad += [f.id for f in self.fixtures if f.room not in room_ids]
        if bad:
            raise ValueError(f"references to unknown rooms: {sorted(bad)}")
        return self

    def room(self, room_id: str) -> Room:
        for r in self.rooms:
            if r.id == room_id:
                return r
        raise KeyError(room_id)

    @property
    def built_area_m2(self) -> float:
        """Area covered by enclosed rooms (open areas such as a courtyard excluded)."""
        return round(sum(r.area_m2 for r in self.rooms if not r.is_open), 1)

    @property
    def plot_area_m2(self) -> float:
        return round(self.plot.width * self.plot.depth / 10_000, 1)

    def to_json_dict(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)
