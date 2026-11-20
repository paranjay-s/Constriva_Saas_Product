"""RoomProgram: what to place (targets and relationships), never where.

Produced by the LLM from the Brief (Phase 4) or written by hand in tests. Contains no
coordinates; the layout step turns it into a FloorPlan.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ai.floorplan.schemas.common import Block, PoolLayout, RoomType, Side, Zone
from app.modules.ai.floorplan.schemas.rules import Rule


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProgramRoom(_Model):
    id: str = Field(min_length=1)
    type: RoomType
    label: str
    target_area_m2: float = Field(gt=0)
    zone: Zone
    attached_to: str | None = Field(
        default=None, description="Room this one must open directly into (e.g. attached bath)"
    )
    block: Block | None = Field(
        default=None, description="Two-block villa: main/guest building; pool = opens on deck"
    )


class Adjacency(_Model):
    a: str
    b: str
    weight: int = Field(default=1, ge=1, le=10)


class RoomProgram(_Model):
    rooms: list[ProgramRoom]
    adjacency: list[Adjacency] = Field(default_factory=list)
    entrance_side: Side | None = None
    pool_layout: PoolLayout | None = None
    pool_axis: Literal["front_back", "side_by_side"] | None = Field(
        default=None,
        description="Two-block villa: blocks in front of/behind the pool, or left/right of it",
    )
    rules: list[Rule] = Field(
        default_factory=list, description="Hard layout rules, room ids resolved (rules.py)"
    )
