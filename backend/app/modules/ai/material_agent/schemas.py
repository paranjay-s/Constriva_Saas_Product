"""Data shapes of the Material Finder (identification + quantities, never money).

Three groups:
  * what the vision model returns (ImageAnalysis / DetectedMaterial): names and coverage
    shares only, no numbers about size or quantity;
  * the space we measure (TargetSpace, RoomGeom) and what we compute (QuantityLine,
    MaterialReport), all produced by plain Python;
  * API bodies and the typed chat intent (ChatIntent).

There is deliberately no field for money anywhere (tests/material_agent guards this).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Surface = Literal[
    "floor",
    "wall",
    "ceiling",
    "countertop",
    "backsplash",
    "cabinet",
    "door",
    "window",
    "facade",
    "stair",
    "railing",
    "furniture",
    "other",
]
SURFACES: tuple[str, ...] = Surface.__args__  # type: ignore[attr-defined]
Confidence = Literal["high", "medium", "low"]
Unit = Literal["ft", "in", "m", "cm", "mm"]
Application = Literal["platform", "floor", "all_walls", "one_wall", "ceiling", "backsplash"]
PlatformLayout = Literal["one_wall", "l_shape", "u_shape", "parallel", "island"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------- vision output


class DetectedMaterial(_Model):
    """One finish the vision model sees. Coverage is a share, never a size."""

    name: str = Field(
        max_length=120,
        description="Specific name, e.g. 'fluted walnut veneer panel', 'Statuario marble'",
    )
    category: str = Field(max_length=40, description="e.g. stone, tile, wood_panel, paint")
    surface: Surface
    location: str = Field(default="", max_length=160, description="Where in the photo")
    coverage_ratio: float | None = Field(
        default=None, ge=0, le=1, description="Share of that surface it covers (0-1)"
    )
    finish: str = Field(default="", max_length=60, description="polished, honed, matte...")
    pattern: str = Field(default="", max_length=60, description="vertical flutes, herringbone...")
    colour: str = Field(default="", max_length=60)
    size_hint: str = Field(default="", max_length=60, description="e.g. '600 x 1200 mm tiles'")
    confidence: Confidence = "medium"
    look_alikes: list[str] = Field(default_factory=list, max_length=4)
    evidence: str = Field(default="", max_length=120, description="Visual cue used, a few words")


class ImageAnalysis(_Model):
    scene: str = Field(default="", max_length=60, description="living room, kitchen, facade...")
    focus_found: bool = Field(default=True, description="False if the asked area is not visible")
    focus_note: str = Field(default="", max_length=200)
    materials: list[DetectedMaterial] = Field(default_factory=list, max_length=12)


# ------------------------------------------------------------ after matching


class Material(_Model):
    """A detected material matched to the catalog (catalog_id None = not in the catalog)."""

    id: str
    catalog_id: str | None = None
    name: str
    display_name: str
    category: str
    surface: Surface
    location: str = ""
    coverage_ratio: float | None = None
    finish: str = ""
    pattern: str = ""
    colour: str = ""
    size_hint: str = ""
    confidence: Confidence = "medium"
    look_alikes: list[str] = Field(default_factory=list)
    evidence: str = ""
    replaces: str = Field(default="", description="Name of the photo material it was swapped for")


# --------------------------------------------------------------- the space


class OpeningGeom(_Model):
    kind: Literal["door", "window"]
    width_ft: float = Field(gt=0)
    height_ft: float = Field(gt=0)
    side: int | None = Field(default=None, description="Index of the room side it is on")


class SideGeom(_Model):
    index: int
    length_ft: float = Field(ge=0)
    label: str = ""


class RoomGeom(_Model):
    """A room in feet: sides in order around the room, openings on them."""

    name: str
    kind: str = ""
    area_sqft: float = Field(ge=0)
    height_ft: float = Field(gt=0)
    sides: list[SideGeom] = Field(default_factory=list)
    openings: list[OpeningGeom] = Field(default_factory=list)
    length_ft: float = 0
    width_ft: float = 0


class WallGeom(_Model):
    width_ft: float = Field(gt=0)
    height_ft: float = Field(gt=0)
    label: str = "Wall"
    openings: list[OpeningGeom] = Field(default_factory=list)


class TargetSpace(_Model):
    source: Literal["manual", "project", "uploaded_plan"]
    label: str = Field(description="Shown in the chip, e.g. 'Kitchen, 10 x 8 ft, from project X'")
    room: RoomGeom | None = None
    wall: WallGeom | None = None
    project_id: str | None = None
    project_name: str | None = None


class ManualSpace(_Model):
    """Dimensions typed by the person. kind=wall: width x height; kind=room: L x W x H."""

    kind: Literal["room", "wall"]
    unit: Unit = "ft"
    length: float = Field(gt=0, le=10000, description="Room length, or wall width")
    width: float | None = Field(default=None, gt=0, le=10000, description="Room width")
    height: float | None = Field(default=None, gt=0, le=10000)
    label: str = Field(default="", max_length=60)
    doors: int = Field(default=0, ge=0, le=20)
    windows: int = Field(default=0, ge=0, le=40)


# ------------------------------------------------------------ calculation


class ApplicationRequest(_Model):
    application: Application
    layout: PlatformLayout | None = None
    depth_ft: float | None = Field(default=None, gt=0, le=10)
    height_ft: float | None = Field(default=None, gt=0, le=40, description="backsplash height")
    side: int | None = Field(default=None, description="for one_wall: which side of the room")


class BreakdownLine(_Model):
    label: str
    formula: str
    value: float


class QuantityLine(_Model):
    material_id: str
    material: str
    application: str = Field(description="e.g. 'TV wall', 'Kitchen platform (L-shape)'")
    surface_sqft: float = Field(description="Area of the surface before the coverage share")
    coverage_ratio: float = Field(ge=0, le=1)
    net_qty: float
    wastage_pct: float
    total_qty: float = Field(description="net_qty plus wastage")
    unit: Literal["sq ft", "rft", "nos"] = "sq ft"
    buy_qty: float | None = None
    buy_unit: str | None = None
    breakdown: list[BreakdownLine] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class SupportLine(_Model):
    """A supporting item (adhesive, grout, primer...) worked out from a material's area."""

    material_id: str
    material: str
    item: str
    qty: float
    unit: str
    basis: str = Field(description="e.g. '84 sq ft / 40 sq ft per bag, rounded up'")


class MaterialReport(_Model):
    version: int = 1
    target: TargetSpace | None = None
    lines: list[QuantityLine] = Field(default_factory=list)
    identified_only: list[str] = Field(
        default_factory=list, description="Material ids shown without a quantity"
    )
    assumptions: list[str] = Field(default_factory=list)
    supporting: list[SupportLine] = Field(default_factory=list)
    explanation: str = ""
    note: str = "Quantities are planning estimates. Verify by site measurement before ordering."


class PieceSize(_Model):
    """The tile / slab / sheet size the person will buy (buy count in pieces)."""

    width_ft: float = Field(gt=0, le=20)
    length_ft: float = Field(gt=0, le=20)
    label: str = Field(default="", max_length=40, description="e.g. '600 x 1200 mm'")


class Overrides(_Model):
    """What the assumptions panel and the chat can change (no new vision call)."""

    wastage_pct: dict[str, float] = Field(default_factory=dict, description="material id -> %")
    coverage_ratio: dict[str, float] = Field(default_factory=dict, description="material id -> 0-1")
    ceiling_height_ft: float | None = Field(default=None, gt=0, le=40)
    piece_size: dict[str, PieceSize] = Field(default_factory=dict, description="material id ->")


# ------------------------------------------------------------------- chat


AdviceTopic = Literal[
    "alternatives",
    "compare",
    "suitability",
    "maintenance",
    "durability",
    "installation",
    "pros_cons",
    "general",
]

ChatAction = Literal[
    "recalculate",
    "apply_all",
    "apply_material",
    "change_focus",
    "explain_material",
    "explain_quantity",
    "use_project",
    "upload_plan",
    "money_question",
    "advise",
    "substitute",
    "supporting_materials",
    "set_coverage",
    "set_piece_size",
    "totals",
    "unclear",
]


class ChatIntent(_Model):
    """One follow-up message turned into a typed request; code does the rest."""

    action: ChatAction
    material: str = Field(default="", max_length=120, description="Material named by the person")
    application: Application | None = None
    room: str = Field(default="", max_length=60)
    project_name: str = Field(default="", max_length=120)
    layout: PlatformLayout | None = None
    focus: str = Field(default="", max_length=120, description="change_focus: the new area")
    length: float | None = Field(default=None, gt=0, le=10000)
    width: float | None = Field(default=None, gt=0, le=10000)
    height: float | None = Field(default=None, gt=0, le=10000)
    depth: float | None = Field(default=None, gt=0, le=100)
    unit: Unit | None = None
    wastage_pct: float | None = Field(default=None, ge=0, le=50)
    question: str = Field(default="", max_length=200, description="unclear: what to ask back")
    other_material: str = Field(
        default="", max_length=120, description="substitute: the new one; advise: compared one"
    )
    topic: AdviceTopic | None = None
    place: str = Field(default="", max_length=60, description="bathroom, outdoor, kitchen floor...")
    percent: float | None = Field(default=None, ge=0, le=100, description="set_coverage")


class Explanation(_Model):
    text: str = Field(max_length=2000)


# -------------------------------------------------------------------- API

ReplyStatus = Literal["ok", "needs_input", "not_found", "failed", "working"]


class ChatMessage(_Model):
    role: Literal["user", "assistant"]
    text: str
    status: ReplyStatus | None = None
    options: list[str] = Field(default_factory=list)


class SessionView(_Model):
    id: str
    project_id: str | None = None
    project_name: str | None = None
    focus: str = ""
    scene: str = ""
    focus_found: bool = True
    focus_note: str = ""
    materials: list[Material] = Field(default_factory=list)
    report: MaterialReport | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    pending_question: ChatMessage | None = None
    uploaded_plan_name: str | None = None
    saved: bool = False


class AnalysisCreated(_Model):
    report_id: str
    job_id: str


class ChatReply(_Model):
    status: ReplyStatus
    message: str
    options: list[str] = Field(default_factory=list)
    job_id: str | None = None
    session: SessionView


class RecalculateRequest(_Model):
    space: ManualSpace | None = None
    overrides: Overrides = Field(default_factory=Overrides)


JobStatus = Literal["queued", "running", "done", "failed"]


class JobEvent(_Model):
    job_id: str
    status: JobStatus
    stage: str = Field(
        description="queued, uploading, analysing_image, matching_materials, parsing_plan, "
        "calculating, writing_summary, done"
    )
    detail: str = ""
    progress: int = Field(ge=0, le=100)
    report_id: str | None = None
    error: str | None = None


class JobState(JobEvent):
    events: list[JobEvent] = Field(default_factory=list)
