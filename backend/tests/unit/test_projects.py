"""
=============================================================================
Construtiva Projects Management Unit Test Suite
=============================================================================
File: tests/unit/test_projects.py
Purpose:
  Tests validation schemas and model integrity for project CRUD operations:
  - Create project schema validation
  - Edit project schema validation
  - Response serialization
=============================================================================
"""

import pytest
from pydantic import ValidationError
from app.modules.projects.schemas import (
    CreateProjectRequest,
    UpdateProjectRequest,
    ProjectResponse,
    DeleteProjectResponse,
)


def test_create_project_schema_valid():
    """
    Verifies valid project creation payload parsing.
    """
    payload = CreateProjectRequest(
        name="Pavilion Serena Residences",
        description="2BHK Residential Flat with Terrace",
        status="active"
    )
    assert payload.name == "Pavilion Serena Residences"
    assert payload.status == "active"
    assert payload.description == "2BHK Residential Flat with Terrace"


def test_create_project_schema_missing_name_fails():
    """
    Verifies that missing project name raises Pydantic ValidationError.
    """
    with pytest.raises(ValidationError):
        CreateProjectRequest(name="")


def test_update_project_schema():
    """
    Verifies that update project payload allows partial updates.
    """
    update_payload = UpdateProjectRequest(name="Updated Title")
    assert update_payload.name == "Updated Title"
    assert update_payload.description is None
    assert update_payload.status is None

    dumped = {k: v for k, v in update_payload.model_dump().items() if v is not None}
    assert dumped == {"name": "Updated Title"}


def test_delete_project_response_schema():
    """
    Verifies delete response model structure.
    """
    resp = DeleteProjectResponse(
        deleted=True,
        project_id="123e4567-e89b-12d3-a456-426614174000",
        message="Deleted successfully"
    )
    assert resp.deleted is True
    assert resp.project_id == "123e4567-e89b-12d3-a456-426614174000"

