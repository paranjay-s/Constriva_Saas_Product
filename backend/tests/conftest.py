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


class FakeDb:
    """An in-memory stand-in for the Supabase client, for read paths.

        FakeDb(jobs=[{...}], projects=[{...}]).table("jobs").select("*").eq("id", x).execute()

    `select`, `order` and `limit` are accepted; `eq` filters the rows. Storage signs any
    path as https://storage.test/<path>.
    """

    def __init__(self, **tables: list[dict]) -> None:
        self.tables = {name: list(rows) for name, rows in tables.items()}
        self.storage = MagicMock()
        self.storage.from_.return_value.create_signed_url.side_effect = lambda path, expires_in: {
            "signedURL": f"https://storage.test/{path}"
        }

    def table(self, name: str) -> "FakeDb._Query":
        return FakeDb._Query(self.tables.get(name, []))

    class _Query:
        def __init__(self, rows: list[dict]) -> None:
            self.rows = rows

        def select(self, *_columns: str) -> "FakeDb._Query":
            return self

        def order(self, *_args, **_kwargs) -> "FakeDb._Query":
            return self

        def eq(self, column: str, value) -> "FakeDb._Query":
            return FakeDb._Query([r for r in self.rows if str(r.get(column)) == str(value)])

        def limit(self, count: int) -> "FakeDb._Query":
            return FakeDb._Query(self.rows[:count])

        def execute(self) -> MagicMock:
            return MagicMock(data=list(self.rows))


@pytest.fixture
def fake_db(monkeypatch):
    """Install a FakeDb wherever the routers and the ownership check read the database.

        db = fake_db(jobs=[...], projects=[...], plans=[...])
    """

    def install(**tables: list[dict]) -> FakeDb:
        db = FakeDb(**tables)
        for module in ("app.modules.plans.router", "app.modules.projects.service"):
            monkeypatch.setattr(f"{module}.get_supabase_client", lambda: db)
        return db

    return install
