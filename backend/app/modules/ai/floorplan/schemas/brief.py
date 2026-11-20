"""Brief: the validated merge of the form and the free-text prompt (typed or spoken).

Lengths in the Brief are in cm, converted from the user's unit at the form edge.
Anything the user did not say stays None and is listed in `unknowns`; nothing is guessed
silently. When form and text disagree, the text wins and the clash goes in `conflicts`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ai.floorplan.schemas.common import Block, PoolLayout, RoomType, Side
from app.modules.ai.floorplan.units import InputUnit

Purpose = Literal["residential", "rental", "commercial", "other"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlotSpec(_Model):
    width_cm: int | None = Field(default=None, gt=0)
    depth_cm: int | None = Field(default=None, gt=0)
    input_unit: InputUnit = "ft"
    shape_assumed: bool = Field(
        default=False, description="True when only the area was given and a ratio was assumed"
    )
    area_basis: Literal["plot", "built_up"] | None = Field(
        default=None, description="What a stated area meant: the plot or the built-up area"
    )
    stated_area_m2: float | None = Field(default=None, gt=0)
    built_up_m2: float | None = Field(
        default=None, gt=0, description="Target built-up area (m2) for the layout"
    )


class RoomRequest(_Model):
    type: RoomType
    count: int = Field(default=1, ge=1, le=12)
    attached_bath: bool = False
    dress_room: bool = False
    label: str | None = None
    block: Block | None = Field(
        default=None, description="Two-block villa only: main or guest building"
    )


class Preference(_Model):
    kind: Literal["adjacent", "near", "away_from", "on_side"]
    a: RoomType
    b: RoomType | None = None
    side: Side | None = None
    text: str = ""


class SetbackRequest(_Model):
    """Setbacks the person stated, in metres; None = the setting's default."""

    front: float | None = Field(default=None, ge=0, le=30)
    side: float | None = Field(default=None, ge=0, le=30)
    rear: float | None = Field(default=None, ge=0, le=30)


class Conflict(_Model):
    field: str
    form_value: str
    text_value: str
    resolution: str = "description value used"


class BriefForm(_Model):
    """What the input form sends. Every field is optional; the free text may fill gaps."""

    plot_width: float | None = Field(default=None, gt=0)
    plot_depth: float | None = Field(default=None, gt=0)
    unit: InputUnit = "ft"
    plot_area: float | None = Field(default=None, gt=0, description="In unit^2, only if no size")
    area_basis: Literal["plot", "built_up"] | None = Field(
        default=None, description="The person's answer: is the stated area the plot or built-up?"
    )
    built_up_share: float | None = Field(
        default=None, gt=0.2, lt=1.0, description="Built-up share of the plot, if asked for"
    )
    purpose: Purpose | None = None
    bedrooms: int | None = Field(default=None, ge=0, le=12)
    bathrooms: int | None = Field(default=None, ge=0, le=12)
    extras: list[RoomType] = Field(default_factory=list)
    road_side: Side | None = None
    pool_layout: PoolLayout | None = None
    project_name: str = Field(default="", max_length=120)
    owner_name: str = Field(default="", max_length=120)
    prompt: str = Field(default="", max_length=4000)


class TextBrief(_Model):
    """What the LLM may extract from the free-text prompt. Unstated fields stay null."""

    plot_width: float | None = Field(default=None, gt=0)
    plot_depth: float | None = Field(default=None, gt=0)
    plot_unit: InputUnit | None = None
    plot_area: float | None = Field(default=None, gt=0)
    plot_area_unit: Literal["sqft", "sqm"] | None = None
    area_basis: Literal["plot", "built_up"] | None = Field(
        default=None,
        description="Only when the words say it: 'plot of 5000 sq ft' -> plot; "
        "'5000 sq ft built-up / covered / construction area' -> built_up",
    )
    built_up_share: float | None = Field(
        default=None, gt=0.2, lt=1.0, description="'60% built-up' -> 0.6; else null"
    )
    setbacks: SetbackRequest | None = Field(
        default=None,
        description="Only setbacks the person states, in metres: 'no setbacks' -> all 0; "
        "'3 m front, 1 m sides' -> front 3, side 1; else null",
    )
    purpose: Purpose | None = None
    bedrooms: int | None = Field(default=None, ge=0, le=12)
    bathrooms: int | None = Field(default=None, ge=0, le=12)
    rooms: list[RoomRequest] = Field(default_factory=list)
    road_side: Side | None = None
    project_name: str | None = None
    owner_name: str | None = None
    preferences: list[Preference] = Field(default_factory=list)
    pool_layout: PoolLayout | None = None
    covered_walkway: bool = False
    unsupported: list[str] = Field(
        default_factory=list, description="Requests this tool cannot do (e.g. second floor)"
    )
    notes: str = ""


class Brief(_Model):
    plot: PlotSpec
    purpose: Purpose | None = None
    bedrooms: int | None = Field(default=None, ge=0, le=12)
    bathrooms: int | None = Field(default=None, ge=0, le=12)
    rooms: list[RoomRequest] = Field(default_factory=list)
    road_side: Side | None = None
    floors: Literal[1] = 1
    project_name: str = ""
    owner_name: str = ""
    preferences: list[Preference] = Field(default_factory=list)
    pool_layout: PoolLayout | None = Field(
        default=None, description="Where the pool sits; None = beside the house (side)"
    )
    covered_walkway: bool = False
    built_up_share: float | None = Field(default=None, gt=0.2, lt=1.0)
    setbacks: SetbackRequest | None = None
    notes: str = ""
    unknowns: list[str] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
