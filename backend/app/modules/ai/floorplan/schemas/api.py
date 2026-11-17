"""Request and response bodies of the floor plan API (/api/v1/ai/floorplans).

The frontend mirrors these with zod in features/floorplan/schemas.ts.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ai.floorplan.schemas.brief import Brief, BriefForm
from app.modules.ai.floorplan.schemas.plan import FloorPlan


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------- brief


class ParseBriefRequest(BriefForm):
    """The form fields plus the free-text (typed or spoken) description."""


class ParseBriefResponse(_Model):
    brief: Brief
    summary: str = Field(description="One line, e.g. '3 bedrooms (1 with attached bath)'")
    warnings: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list, description="Needed before generating")
    ready: bool


# ---------------------------------------------------------------- generate


class GenerateRequest(_Model):
    brief: Brief = Field(description="The brief the person confirmed on the card")
    project_id: str | None = Field(default=None, max_length=64)


class JobCreated(_Model):
    job_id: str


JobStatus = Literal["queued", "running", "done", "failed"]


class JobEvent(_Model):
    """One progress step. Also the payload of every SSE `progress` event."""

    job_id: str
    status: JobStatus
    stage: str = Field(description="queued, feasibility, program, layout, checking, saving, done")
    detail: str = ""
    progress: int = Field(ge=0, le=100)
    plan_id: str | None = None
    error: str | None = None
    options: list[str] = Field(default_factory=list, description="What to try when it failed")


class JobState(JobEvent):
    events: list[JobEvent] = Field(default_factory=list)


# -------------------------------------------------------------------- plans


class ChatMessage(_Model):
    role: Literal["user", "assistant"]
    text: str
    status: str | None = None  # assistant replies: ok, impossible, needs_clarification...
    version: int | None = None  # plan version after this message


class PlanResponse(_Model):
    id: str
    project_id: str | None = None
    name: str
    version: int
    plan: FloorPlan
    svg: str
    brief: Brief | None = None
    notes: list[str] = Field(default_factory=list)
    messages: list[ChatMessage] = Field(default_factory=list)
    plan_json: dict = Field(description="Legacy PlanJSON in metres, for the 3D viewer and BOQ")
    saved: bool = Field(description="False if the database was unreachable (kept in memory)")


class EditRequest(_Model):
    message: str = Field(min_length=1, max_length=2000)
    allow_reflow: bool = Field(
        default=True, description="Other rooms may move to make room for the change"
    )
    version: int | None = Field(
        default=None, description="Version the person was looking at; refused if outdated"
    )


class EditResponse(_Model):
    status: Literal["ok", "no_change", "impossible", "needs_clarification", "failed"]
    message: str = ""
    summary: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    plan: PlanResponse
