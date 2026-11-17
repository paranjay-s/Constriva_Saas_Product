import json
from pathlib import Path

import pytest

from app.modules.ai.floorplan.schemas.plan import FloorPlan

FIXTURES = Path(__file__).parent / "fixtures"


def load_sample_dict() -> dict:
    return json.loads((FIXTURES / "sample_plan.json").read_text(encoding="utf-8"))


@pytest.fixture
def sample_dict() -> dict:
    return load_sample_dict()


@pytest.fixture
def sample_plan() -> FloorPlan:
    return FloorPlan.model_validate(load_sample_dict())
