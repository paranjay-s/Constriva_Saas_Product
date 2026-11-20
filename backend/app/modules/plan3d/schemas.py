"""Request and response models of /api/v1/3d."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Our names for a build, and what PlanTo3D calls it. "high" is the cinema video tour.
Quality = Literal["low", "high"]


class QualityInfo(BaseModel):
    id: Quality
    label: str
    description: str
    available: bool
    reason: str = ""


class SystemStatus(BaseModel):
    """Whether the 3D builder can take plans, and what is missing when it cannot."""

    reachable: bool
    ready: bool
    checks: dict = Field(default_factory=dict)
    qualities: list[QualityInfo]
    detail: str = ""


class JobCreated(BaseModel):
    job_id: str


class JobStatus(BaseModel):
    """A job as our pages show it. `stage` is PlanTo3D's: uploaded, detecting, detected,
    queued, building, done or failed."""

    model_config = ConfigDict(extra="ignore")

    job_id: str
    name: str = ""
    project_id: str | None = None
    source: str = "upload"
    stage: str
    progress: int = 0
    message: str = ""
    floors: list[str] = Field(default_factory=list)
    scale_source: str | None = None
    eta_left: int | None = None  # seconds, while building
    queue_position: int | None = None  # 1 = next, while queued
    quality: Quality | None = None  # of the house that is built, or being built
    build_seconds: int | None = None
    # while High builds, a Low house can be walked through (replaced when High is done)
    preview: bool = False
    # rendered video tours: quality -> {file, seconds}
    tours: dict[str, dict[str, Any]] = Field(default_factory=dict)
    # High stills: mode (evening, day) -> {files: [{name, title, file}], tour (the fast tour's
    # mp4), seconds, per_still}; files are under the job's files_url
    stills: dict[str, dict[str, Any]] = Field(default_factory=dict)
    # while stills or a tour render: pictures done and to do
    frames_done: int | None = None
    frames_total: int | None = None
    created_at: str | None = None
    # who read the plan: detector (PlanTo3D's own), ai (our AI plan parser), stored (our floor
    # plan generator), trace (nothing could be read: traced by hand); "" before it is read
    reader: str = ""
    notice: str = ""  # what the person should check, from the reader


class NotificationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: bool


class FromFloorplan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1, max_length=64)


class BuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quality: Quality = "low"


class EmbedAccess(BaseModel):
    """Where to point an iframe. Every URL carries a signed token that expires."""

    base_url: str  # /api/v1/3d/embed/<token>
    expires_in: int
    review_url: str | None = None
    walkthrough_url: str | None = None
    furniture_url: str
    files_url: str | None = None  # the job's files: house.glb, house_blender.zip ...


class ExportReady(BaseModel):
    file: str  # name of the file under the job's `files_url`


class StillsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["evening", "day"] = "evening"


class TourRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quality: Literal["high", "ultra"]
    mode: Literal["evening", "day"] = "evening"
