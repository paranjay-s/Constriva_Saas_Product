"""PlanJSON: the one schema every producer and consumer of a floor plan agrees on.

Producers: the PDF parser (parsing/llm_parser.py) and the plan generators.
Consumers: the material calculator (sheets/llm_mapper.py) and the 3D viewer.

Schema 2.0 only adds fields to 1.x. No key was renamed or removed, so a 1.x document
still validates and every 1.x reader still finds the keys it reads. Where 2.0 introduces a
second name for an existing value (`sill_height` for `sill`, `is_exterior` for `kind`) the
model keeps the two in step.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.plans.room_types import BoqType

SCHEMA_VERSION = "2.0"

# What `wall_height` holds when the drawing does not state a height
# (`wall_height_source == "default"`). The 3D viewer draws walls at this height; the
# material calculator replaces it with its own standard ceiling height.
UNSTATED_WALL_HEIGHT_M = 2.8

Point = Annotated[list[float], Field(min_length=2, max_length=2)]

WallKind = Literal["exterior", "interior"]
RoomKind = Literal["indoor", "semi_open", "outdoor", "void"]
OpeningType = Literal["door", "window"]
BuildingType = Literal["villa", "apartment", "other"]
WallHeightSource = Literal["stated", "default"]
# 1.x wrote scale_text / user_reference; 2.0 writes scale_bar / stated_scale. All are valid.
ScaleSource = Literal[
    "dimension_label",
    "scale_bar",
    "stated_scale",
    "assumed",
    "scale_text",
    "user_reference",
]


class _PlanModel(BaseModel):
    """Keys this schema does not define are kept, not dropped.

    Other readers own keys of their own on the same document. The 3D adapter, for one,
    reads `room.type`, `wall.height` and `level.furniture`. Validating a stored plan must
    never remove them.
    """

    model_config = ConfigDict(extra="allow")


class Wall(_PlanModel):
    id: str
    start: Point
    end: Point
    thickness: float = 0.2
    kind: WallKind | None = None
    is_exterior: bool | None = None
    inferred: bool = False

    @model_validator(mode="after")
    def _sync_exterior(self) -> "Wall":
        if self.kind is None and self.is_exterior is not None:
            self.kind = "exterior" if self.is_exterior else "interior"
        elif self.kind is not None:
            self.is_exterior = self.kind == "exterior"
        return self


class Opening(_PlanModel):
    id: str
    wall_id: str
    type: OpeningType
    offset: float
    width: float
    height: float
    sill: float = 0.0
    sill_height: float | None = None
    # Centre of the opening on its wall, in plan coordinates. Derived from wall + offset.
    position: Point | None = None
    inferred: bool = False

    @model_validator(mode="after")
    def _sync_sill(self) -> "Opening":
        if self.sill_height is None:
            self.sill_height = self.sill
        elif "sill" not in self.model_fields_set:
            self.sill = self.sill_height
        return self


class Column(_PlanModel):
    id: str
    position: Point
    width: float = 0.23
    depth: float = 0.23


class Room(_PlanModel):
    id: str
    name: str | None = None
    kind: RoomKind | None = None
    # How the material calculator counts the room. Starts from `kind` and differs from it
    # for parking and driveways (outdoor) and for semi-open wet rooms (indoor). `kind`
    # itself is the 3D adapter's and is never changed. None on plans stored before this
    # field existed; the calculator then derives it.
    boq_kind: RoomKind | None = None
    # What the room is used for, for the material calculator. Only rooms whose `boq_kind`
    # is indoor have one; None otherwise and on plans stored before this field existed.
    # This is not `type`: that key belongs to the 3D adapter and is never read or written.
    boq_type: BoqType | None = None
    polygon: list[Point]
    # Ceiling height of this room when it differs from the level's wall_height.
    height_m: float | None = None
    is_double_height_void: bool = False


class Level(_PlanModel):
    index: int = 0
    name: str | None = None
    elevation: float = 0.0
    wall_height: float = 3.0
    wall_height_source: WallHeightSource = "default"
    walls: list[Wall] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)
    rooms: list[Room] = Field(default_factory=list)
    columns: list[Column] = Field(default_factory=list)


class ParserInfo(_PlanModel):
    """Which parser run produced this plan. Lets a stored plan be matched to its PDF."""

    pdf_sha256: str | None = None
    parser_version: str | None = None
    prompt_version: str | None = None
    provider: str | None = None
    model: str | None = None
    # What the parse cost: tokens billed over every model call it made, and how many calls.
    input_tokens: int | None = None
    output_tokens: int | None = None
    attempts: int | None = None


class PlanJSON(_PlanModel):
    schema_version: str = SCHEMA_VERSION
    version: int = 1
    units: Literal["m"] = "m"
    building_type: BuildingType = "other"
    scale_source: ScaleSource = "assumed"
    project_title: str | None = None
    subject: str | None = None
    client: str | None = None
    architect: str | None = None
    levels: list[Level] = Field(default_factory=list)
    confidence: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    parser: ParserInfo | None = None
