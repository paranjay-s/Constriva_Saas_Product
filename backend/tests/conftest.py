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
# Tests must not read or write the developer's real parsed-plan cache.
os.environ["PLAN_PARSER_CACHE"] = "off"

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import AuthenticatedUser, get_current_user


@pytest.fixture(autouse=True)
def no_live_llm(monkeypatch):
    """Unit tests never call a live model.

    The plan parser builds its real client only when it is not handed one. Any test that
    reaches that point fails here instead of spending money on a provider.
    """

    def refuse() -> None:
        raise AssertionError("A test tried to build a live LLM client. Pass a fake client.")

    monkeypatch.setattr("app.modules.parsing.llm_parser.build_client", refuse)


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
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated_client() -> TestClient:
    """
    FastAPI TestClient without dependency overrides for auth and public endpoint testing.
    """
    app.dependency_overrides.clear()
    test_client = TestClient(app)
    yield test_client
