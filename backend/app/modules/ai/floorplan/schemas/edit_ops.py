"""Typed edit operations. The LLM returns a list of these; the edit engine applies them.

Rooms not named by any operation are locked during re-layout. Drag and drop in the UI
will emit the same operations.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ai.floorplan.schemas.common import PoolLayout, RoomType, Side
from app.modules.ai.floorplan.units import DisplayUnit

Anchor = Literal[
    "north", "south", "east", "west", "north-east", "north-west", "south-east", "south-west"
]


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResizeRoom(_Op):
    op: Literal["resize_room"]
    id: str
    width_cm: int | None = Field(default=None, gt=0)
    height_cm: int | None = Field(default=None, gt=0)
    change: Literal["bigger", "smaller"] | None = Field(
        default=None, description="Used when no size is given; no size and no change = bigger"
    )


class MoveRoom(_Op):
    op: Literal["move_room"]
    id: str
    anchor: Anchor | None = None
    next_to: str | None = None


class SwapRooms(_Op):
    op: Literal["swap_rooms"]
    a: str
    b: str


class AddRoom(_Op):
    op: Literal["add_room"]
    type: RoomType
    label: str | None = None
    target_area_m2: float | None = Field(default=None, gt=0)
    next_to: str | None = None


class RemoveRoom(_Op):
    op: Literal["remove_room"]
    id: str


class RenameRoom(_Op):
    op: Literal["rename_room"]
    id: str
    label: str = Field(min_length=1)


class SetPlot(_Op):
    op: Literal["set_plot"]
    width_cm: int = Field(gt=0)
    depth_cm: int = Field(gt=0)


class MoveDoor(_Op):
    op: Literal["move_door"]
    id: str
    offset: int | None = Field(default=None, ge=0)
    wall: Side | None = None


class AddWindow(_Op):
    op: Literal["add_window"]
    room: str
    wall: Side | None = None  # None: the room's best outside wall
    width: int = Field(default=120, gt=0)
    offset: int | None = Field(default=None, ge=0)


class SetPoolLayout(_Op):
    """Move the pool: beside the house, U-shaped house around it, in the middle, or
    between two blocks. Re-plans the whole layout (like set_plot)."""

    op: Literal["set_pool_layout"]
    layout: PoolLayout


# ---------------------------------------------------------- whole-plan changes
# Each of these must be the only operation in a request (walls are named by compass side,
# so mixing them with other operations would be ambiguous).


class SetFacing(_Op):
    """Turn the house so its road / main entrance is on this side ("make it east facing").
    The layout turns with it: every room keeps its neighbours, doors and furniture."""

    op: Literal["set_facing"]
    side: Side


class RotatePlan(_Op):
    op: Literal["rotate_plan"]
    degrees: Literal[90, 180, 270] = Field(description="Clockwise")


class MirrorPlan(_Op):
    """Mirror image of the plan: left_right swaps east and west, top_bottom north and south."""

    op: Literal["mirror_plan"]
    axis: Literal["left_right", "top_bottom"] = "left_right"


class Undo(_Op):
    """Go back one change, or to a given version number."""

    op: Literal["undo"]
    version: int | None = Field(default=None, ge=1)


# ------------------------------------------------------------ rooms and openings


class ChangeRoomType(_Op):
    """Use a room for something else ("make the study a bedroom"); size and place stay."""

    op: Literal["change_room_type"]
    id: str
    type: RoomType
    label: str | None = None


class AddDoor(_Op):
    op: Literal["add_door"]
    room: str
    to: str = Field(description="Another room id, or 'outside'")
    wall: Side | None = None
    width: int | None = Field(default=None, gt=0)


class RemoveDoor(_Op):
    op: Literal["remove_door"]
    id: str


class SetDoorWidth(_Op):
    op: Literal["set_door_width"]
    id: str
    width: int = Field(gt=0)


class RemoveWindow(_Op):
    op: Literal["remove_window"]
    id: str


class SetWindowWidth(_Op):
    op: Literal["set_window_width"]
    id: str
    width: int = Field(gt=0)


class SetUnits(_Op):
    """Show sizes on the drawing in feet, metres or centimetres."""

    op: Literal["set_units"]
    unit: DisplayUnit


WHOLE_PLAN_OPS = (SetFacing, RotatePlan, MirrorPlan)


EditOp = Annotated[
    ResizeRoom
    | MoveRoom
    | SwapRooms
    | AddRoom
    | RemoveRoom
    | RenameRoom
    | SetPlot
    | MoveDoor
    | AddWindow
    | SetPoolLayout
    | SetFacing
    | RotatePlan
    | MirrorPlan
    | Undo
    | ChangeRoomType
    | AddDoor
    | RemoveDoor
    | SetDoorWidth
    | RemoveWindow
    | SetWindowWidth
    | SetUnits,
    Field(discriminator="op"),
]


class EditOpList(BaseModel):
    ops: list[EditOp]
