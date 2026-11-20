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


@pytest.fixture(autouse=True)
def _whole_plot_layouts(request, monkeypatch):
    """Tests written before setbacks and the built-up target lay out the whole plot.
    Tests marked `site_rules` run with the shipped defaults."""
    from app.modules.ai.floorplan.settings import get_settings

    if request.node.get_closest_marker("site_rules") is None:
        monkeypatch.setattr(get_settings(), "site_rules", False)
