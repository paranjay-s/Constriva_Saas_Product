"""Request and response models of the BOQ endpoints (/api/v1/sheets/boq)."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

BoqJobStatus = Literal["queued", "running", "done", "failed"]


class BoqJobCreated(BaseModel):
    job_id: str


class BoqJobEvent(BaseModel):
    job_id: str
    status: BoqJobStatus
    stage: str = Field(description="queued, uploading, parsing, calculating, done or failed")
    detail: str = ""
    progress: int = Field(ge=0, le=100)
    error: str | None = None
    error_code: str | None = None


class BoqJobState(BoqJobEvent):
    events: list[BoqJobEvent] = Field(default_factory=list)


class BoqComponent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = Field(max_length=200)
    quantity: float
    unit: str = Field(max_length=40)
    quantity_decimals: int | None = Field(default=None, ge=0, le=4)


class BoqItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    serial_no: int | str
    item_code: str = Field(max_length=80)
    category_code: str | None = Field(default=None, max_length=8)
    category: str = Field(max_length=120)
    sub_category: str = Field(max_length=120)
    name: str = Field(max_length=300)
    unit: str = Field(max_length=40)
    quantity: float
    quantity_decimals: int | None = Field(default=None, ge=0, le=4)
    components: list[BoqComponent] = Field(default_factory=list, max_length=40)
    calc_type: Literal["geometry", "count", "allowance"] = "geometry"
    quote_status: Literal["INCLUDED", "EXCLUDED_FROM_QUOTE"] = "INCLUDED"
    note: str = Field(default="", max_length=2000)


class BoqExportRequest(BaseModel):
    """The rows of a BOQ result, sent back unchanged to be rendered as a file."""

    items: list[BoqItem] = Field(max_length=500)
    warnings: list[str] = Field(default_factory=list, max_length=200)
    geometry_summary: dict[str, Any] = Field(default_factory=dict)
    project_metadata: dict[str, Any] = Field(default_factory=dict)
