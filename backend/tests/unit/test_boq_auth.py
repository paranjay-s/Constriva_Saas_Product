"""The BOQ endpoints authenticate exactly as the project endpoints do.

Both use the app's one auth dependency, `get_current_user`. These tests pin that, so a BOQ
endpoint can never be left more open than a project endpoint.
"""

import pytest

from app.core.security import get_current_user
from app.main import app

BOQ = "/api/v1/sheets/boq"
PROJECTS = "/api/v1/projects"

BOQ_ENDPOINTS = [
    ("POST", BOQ),
    ("GET", f"{BOQ}/jobs/abc"),
    ("GET", f"{BOQ}/jobs/abc/events"),
    ("GET", f"{BOQ}/jobs/abc/result"),
    ("POST", f"{BOQ}/jobs/abc/recalculate"),
    ("POST", f"{BOQ}/export/pdf"),
    ("POST", f"{BOQ}/export/xlsx"),
]


def operations_under(prefix: str) -> dict[tuple[str, str], dict]:
    """{(METHOD, path): operation} from the app's OpenAPI document."""
    found = {}
    for path, item in app.openapi()["paths"].items():
        if path == prefix or path.startswith(prefix + "/"):
            for method, operation in item.items():
                found[(method.upper(), path)] = operation
    return found


def test_every_boq_endpoint_declares_the_same_auth_as_project_endpoints():
    boq = operations_under(BOQ)
    assert sorted(boq) == sorted(
        [
            ("POST", BOQ),
            ("GET", f"{BOQ}/jobs/{{job_id}}"),
            ("GET", f"{BOQ}/jobs/{{job_id}}/events"),
            ("GET", f"{BOQ}/jobs/{{job_id}}/result"),
            ("POST", f"{BOQ}/jobs/{{job_id}}/recalculate"),
            ("POST", f"{BOQ}/export/pdf"),
            ("POST", f"{BOQ}/export/xlsx"),
        ]
    )
    bearer = [{"HTTPBearer": []}]
    assert all(op.get("security") == bearer for op in boq.values()), [
        key for key, op in boq.items() if op.get("security") != bearer
    ]

    # the project endpoints it must match (their health probe aside)
    projects = {k: v for k, v in operations_under(PROJECTS).items() if not k[1].endswith("/ping")}
    assert projects and all(op.get("security") == bearer for op in projects.values())


def test_the_boq_router_uses_the_one_auth_dependency():
    import inspect

    from app.modules.sheets import boq_router

    source = inspect.getsource(boq_router)
    assert "User = Annotated[AuthenticatedUser, Depends(get_current_user)]" in source
    assert boq_router.get_current_user is get_current_user
    for endpoint in (
        boq_router.start_boq,
        boq_router.boq_job_state,
        boq_router.boq_job_events,
        boq_router.boq_job_result,
        boq_router.recalculate_boq_job,
        boq_router.export_boq_pdf,
        boq_router.export_boq_xlsx,
    ):
        assert inspect.signature(endpoint).parameters["user"].annotation is boq_router.User


@pytest.mark.parametrize(("method", "url"), BOQ_ENDPOINTS)
@pytest.mark.parametrize("token", ["not-a-jwt", "aaa.bbb.ccc"])
def test_a_bad_token_is_refused_on_every_boq_endpoint(unauthenticated_client, method, url, token):
    response = unauthenticated_client.request(
        method, url, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert "sign in again" in response.json()["detail"].lower()


def test_project_endpoints_refuse_the_same_bad_token_the_same_way(unauthenticated_client):
    response = unauthenticated_client.get(PROJECTS, headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401
    assert "sign in again" in response.json()["detail"].lower()
