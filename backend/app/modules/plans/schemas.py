from typing import Annotated, Literal

from pydantic import BaseModel, Field

Point = Annotated[list[float], Field(min_length=2, max_length=2)]


class Wall(BaseModel):
    id: str
    start: Point
    end: Point
    thickness: float = 0.2
    kind: Literal["exterior", "interior"] | None = None
    inferred: bool = False


class Opening(BaseModel):
    id: str
    wall_id: str
    type: Literal["door", "window"]
    offset: float
    width: float
    height: float
    sill: float = 0.0
    inferred: bool = False


class Column(BaseModel):
    id: str
    position: Point
    width: float = 0.23
    depth: float = 0.23


class Room(BaseModel):
    id: str
    name: str | None = None
    kind: Literal["indoor", "semi_open", "outdoor", "void"] | None = None
    polygon: list[Point]


class Level(BaseModel):
    elevation: float = 0.0
    wall_height: float = 3.0
    walls: list[Wall] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)
    rooms: list[Room] = Field(default_factory=list)
    columns: list[Column] = Field(default_factory=list)


class PlanJSON(BaseModel):
    version: int = 1
    units: Literal["m"] = "m"
    scale_source: Literal["scale_text", "dimension_label", "user_reference", "assumed"] = "assumed"
    project_title: str | None = None
    subject: str | None = None
    client: str | None = None
    architect: str | None = None
    levels: list[Level] = Field(default_factory=list)
    confidence: dict[str, float] = Field(default_factory=dict)
