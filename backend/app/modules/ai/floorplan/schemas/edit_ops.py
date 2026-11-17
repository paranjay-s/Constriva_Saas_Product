"""Typed edit operations. The LLM returns a list of these; the edit engine applies them.

Rooms not named by any operation are locked during re-layout. Drag and drop in the UI
will emit the same operations.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ai.floorplan.schemas.common import PoolLayout, RoomType, Side

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
    | SetPoolLayout,
    Field(discriminator="op"),
]


class EditOpList(BaseModel):
    ops: list[EditOp]
