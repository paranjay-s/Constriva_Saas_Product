"""
=============================================================================
Construtiva API Smoke & Health Tests
=============================================================================
File: tests/unit/test_api.py
Purpose:
  Verifies core FastAPI health check and status probes across all mounted modules.
=============================================================================
"""

import pytest
from fastapi.testclient import TestClient

STUB_MODULES = ["sheets", "materials", "ai", "loan", "jobs"]


def test_health(client: TestClient) -> None:
    """
    Verifies the /health probe returns HTTP 200 and application identification metadata.
    """
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "Construtiva" in payload["app"]


@pytest.mark.parametrize("name", STUB_MODULES)
def test_stub_module_ping(client: TestClient, name: str) -> None:
    """
    Verifies stub modules respond to /ping with HTTP 200.
    """
    response = client.get(f"/api/v1/{name}/ping")
    assert response.status_code == 200
    assert response.json()["module"] == name
