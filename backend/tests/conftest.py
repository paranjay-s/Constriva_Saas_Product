"""
=============================================================================
Construtiva Backend Test Configuration & Shared Fixtures
=============================================================================
File: tests/conftest.py
Purpose:
  Provides shared pytest fixtures for FastAPI endpoint and unit testing:
  - Sets TESTING=1 environment flag to bypass network-bound storage verification.
  - Configures authenticated mock sessions for protected routes.
  - Sets up reusable mock Supabase query builders and test client instances.
=============================================================================
"""

import os
os.environ["TESTING"] = "1"

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import AuthenticatedUser, get_current_user


@pytest.fixture
def mock_user() -> AuthenticatedUser:
    """
    Provides a standardized mock authenticated architect user.
    """
    return AuthenticatedUser(
        user_id="test-architect-uuid-0001",
        email="architect@construtiva.ai",
        metadata={"full_name": "Senior Architect Demo"}
    )


@pytest.fixture
def client(mock_user: AuthenticatedUser) -> TestClient:
    """
    FastAPI TestClient with authenticated user dependency override.
    """
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated_client() -> TestClient:
    """
    FastAPI TestClient without dependency overrides for auth and public endpoint testing.
    """
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
