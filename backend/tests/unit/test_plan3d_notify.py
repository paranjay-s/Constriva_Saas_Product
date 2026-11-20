"""Build emails and in-app notifications (plan3d/notify.py), with a fake mailer and the fake
PlanTo3D of test_plan3d.py. No email is ever sent."""

# ruff: noqa: F811  (the `planto3d` fixture is imported from test_plan3d and used by name)

import logging

import pytest

from app.modules.plan3d import notify
from tests.unit.test_plan3d import API, planto3d, upload  # noqa: F401


class FakeMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


@pytest.fixture
def mailer():
    notify.reset()
    fake = FakeMailer()
    notify.set_mailer(fake)
    yield fake
    notify.set_mailer(None)
    notify.reset()


def build(client, job_id: str, quality: str) -> None:
    assert client.post(f"{API}/jobs/{job_id}/build", json={"quality": quality}).status_code == 200


def finish(planto3d, job_id: str, stage: str) -> None:
    planto3d.jobs[job_id].update(stage=stage)


def test_a_high_build_sends_one_email_and_one_notification(client, planto3d, mailer, mock_user):
    job = upload(client)
    build(client, job, "high")
    finish(planto3d, job, "done")
    for _ in range(3):  # seen three times, announced once
        client.get(f"{API}/jobs/{job}")
    assert len(mailer.sent) == 1
    to, subject, body = mailer.sent[0]
    assert to == mock_user.email and subject == "Your 3D house is ready"
    assert f"/3d/{job}" in body and "sign in" in body
    assert "house.pdf" not in body  # no plan contents
    items = client.get(f"{API}/notifications").json()["items"]
    assert [(i["job_id"], i["outcome"]) for i in items] == [(job, "done")]


def test_a_failed_build_is_announced_too(client, planto3d, mailer):
    job = upload(client)
    build(client, job, "high")
    finish(planto3d, job, "failed")
    client.get(f"{API}/jobs/{job}")
    assert [s[1] for s in mailer.sent] == ["Your 3D house could not be built"]


def test_a_low_build_is_not_announced(client, planto3d, mailer):
    job = upload(client)
    build(client, job, "low")
    finish(planto3d, job, "done")
    client.get(f"{API}/jobs/{job}")
    assert mailer.sent == [] and client.get(f"{API}/notifications").json()["items"] == []


def test_the_email_can_be_turned_off_the_notification_stays(client, planto3d, mailer):
    assert client.get(f"{API}/notifications").json()["email"] is True  # on by default
    assert client.put(f"{API}/notifications/settings", json={"email": False}).json() == {
        "email": False
    }
    job = upload(client)
    build(client, job, "high")
    finish(planto3d, job, "done")
    client.get(f"{API}/jobs/{job}")
    assert mailer.sent == []
    assert len(client.get(f"{API}/notifications").json()["items"]) == 1


def test_without_smtp_the_email_is_logged_not_sent(caplog):
    with caplog.at_level(logging.INFO, logger="construtiva.plan3d.notify"):
        notify.LogMailer().send("owner@example.com", "Your 3D house is ready", "link")
    assert "not sent" in caplog.text and "owner@example.com" not in caplog.text


def test_furniture_changes_are_off_by_default():
    from app.modules.plan3d.settings import Plan3dSettings

    assert Plan3dSettings().allow_furniture_changes is False
