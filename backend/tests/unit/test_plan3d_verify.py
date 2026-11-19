"""The AI second look (plan3d/verify.py) with a fake client: no live model."""

import pytest

from app.modules.plan3d import verify

PLAN = {
    "floors": [
        {
            "name": "Ground Floor",
            "rooms": [{"label": "KITCHEN", "type": "kitchen", "rects": [[0, 10, 0, 12]]}],
            "openings": [{"type": "door", "rect": [4, 7, -0.2, 0.2]}],
        }
    ],
    "checks": [{"floor": 0, "kind": "unknown_label", "item": ["room", 0], "message": "x"}],
}


class FakeClient:
    provider, model, last_usage = "fake", "fake", None

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(self, *, system_prompt, images, text, json_schema=None):
        self.calls += 1
        assert images and "KITCHEN [kitchen], 120 sq ft, 1 doors, 0 windows" in text
        return {
            "differences": [
                {"kind": "missing_room", "storey": "Ground Floor", "room": "STORE",
                 "message": "A store next to the kitchen was not read.", "confidence": 0.8},
                {"kind": "nonsense", "message": "dropped", "confidence": 0.9},
                {"kind": "other", "message": "", "confidence": 0.9},
            ]
        }  # fmt: skip


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(verify, "CACHE", tmp_path)


def test_differences_are_validated_and_cached(cache):
    client = FakeClient()
    found = verify.differences(PLAN, b"png", client)
    assert [d["kind"] for d in found] == ["missing_room"] and found[0]["room"] == "STORE"
    assert verify.differences(PLAN, b"png", client) == found and client.calls == 1


class FakeService:
    def __init__(self) -> None:
        self.saved = None

    async def plan(self, job_id):
        return {**PLAN, "checks": list(PLAN["checks"])}

    async def page_png(self, job_id):
        return b"png"

    async def save_plan(self, job_id, plan):
        self.saved = plan


async def test_review_adds_its_findings_to_needs_checking_once(cache):
    svc = FakeService()
    verify._done.discard("j1")
    n = await verify.review(
        "j1", svc, ask=lambda plan, page: verify.differences(plan, page, FakeClient())
    )
    assert n == 1
    kinds = [c["kind"] for c in svc.saved["checks"]]
    assert kinds == ["unknown_label", "ai_review"]
    assert "Ground Floor" in svc.saved["checks"][1]["message"]
    assert await verify.review("j1", svc) == 0
