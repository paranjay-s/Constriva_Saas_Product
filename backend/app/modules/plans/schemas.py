"""PlanJSON: the one schema every producer and consumer of a floor plan agrees on.

Producers: the PDF parser (parsing/llm_parser.py) and the plan generators.
Consumers: the material calculator (sheets/llm_mapper.py) and the 3D viewer.

Schema 2.0 only adds fields to 1.x. No key was renamed or removed, so a 1.x document
still validates and every 1.x reader still finds the keys it reads. Where 2.0 introduces a
second name for an existing value (`sill_height` for `sill`, `is_exterior` for `kind`) the
model keeps the two in step.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

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


class Wall(BaseModel):
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


class Opening(BaseModel):
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


class Column(BaseModel):
    id: str
    position: Point
    width: float = 0.23
    depth: float = 0.23


class Room(BaseModel):
    id: str
    name: str | None = None
    kind: RoomKind | None = None
    polygon: list[Point]
    # Ceiling height of this room when it differs from the level's wall_height.
    height_m: float | None = None
    is_double_height_void: bool = False


class Level(BaseModel):
    index: int = 0
    name: str | None = None
    elevation: float = 0.0
    wall_height: float = 3.0
    wall_height_source: WallHeightSource = "default"
    walls: list[Wall] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)
    rooms: list[Room] = Field(default_factory=list)
    columns: list[Column] = Field(default_factory=list)


class ParserInfo(BaseModel):
    """Which parser run produced this plan. Lets a stored plan be matched to its PDF."""

    pdf_sha256: str | None = None
    parser_version: str | None = None
    prompt_version: str | None = None
    provider: str | None = None
    model: str | None = None


class PlanJSON(BaseModel):
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
