"""app/modules/parsing/schemas.py - Request and response models for the parsing module."""

from pydantic import BaseModel


class ParseRequest(BaseModel):
    file_id: str
    project_id: str
    page_number: int = 1


class ParseResponse(BaseModel):
    job_id: str
    status: str = "queued"
    message: str = "Parsing job initiated"
