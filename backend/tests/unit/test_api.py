import pytest
from fastapi.testclient import TestClient

from app.main import app

MODULES = ["projects", "files", "plans", "parsing", "sheets", "materials", "ai", "loan", "jobs"]
client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("name", MODULES)
def test_module_ping(name: str) -> None:
    response = client.get(f"/api/v1/{name}/ping")
    assert response.status_code == 200
    assert response.json()["module"] == name

