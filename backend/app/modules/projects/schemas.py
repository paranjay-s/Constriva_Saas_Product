"""
=============================================================================
Construtiva Projects Management Pydantic Schemas
=============================================================================
File: app/modules/projects/schemas.py
Purpose:
  Defines request and response schemas for project lifecycle operations:
  - Create project (POST)
  - Read project details and active plan (GET)
  - Edit project title, description, or status (PUT / PATCH)
  - Delete project (DELETE)
  - Comprehensive projects list with metadata (GET /all)
=============================================================================
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    """
    Payload for creating a new property / building project.
    """
    name: str = Field(..., min_length=1, description="Project title (e.g. 'Pavilion Serena Residences')")
    description: Optional[str] = Field(None, description="Optional brief project summary or notes")
    status: str = Field("active", description="Project status: 'active' or 'archived'")


class UpdateProjectRequest(BaseModel):
    """
    Payload for editing an existing project.
    """
    name: Optional[str] = Field(None, min_length=1, description="Updated project title")
    description: Optional[str] = Field(None, description="Updated project summary")
    status: Optional[str] = Field(None, description="Updated status: 'active' or 'archived'")


class ProjectResponse(BaseModel):
    """
    Standard project representation returned by API endpoints.
    """
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    active_plan: Optional[Dict[str, Any]] = None


class ProjectListResponse(BaseModel):
    """
    Wrapper response containing collection of projects and total count.
    """
    projects: List[ProjectResponse]
    total_count: int


class DeleteProjectResponse(BaseModel):
    """
    Confirmation response after project deletion.
    """
    deleted: bool
    project_id: str
    message: str
