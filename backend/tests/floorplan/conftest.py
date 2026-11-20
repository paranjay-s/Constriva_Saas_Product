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


@pytest.fixture(autouse=True, scope="session")
def _whole_plot_by_default():
    """Tests written before setbacks, the built-up target and the Dubai Building Code
    minimums lay out the whole plot (module fixtures too)."""
    from app.modules.ai.floorplan.settings import get_settings

    s = get_settings()
    before = s.site_rules
    s.site_rules = False
    yield
    s.site_rules = before


@pytest.fixture(autouse=True)
def _whole_plot_layouts(request, monkeypatch):
    """Tests marked `site_rules` run with the shipped defaults."""
    from app.modules.ai.floorplan.settings import get_settings

    marked = request.node.get_closest_marker("site_rules") is not None
    monkeypatch.setattr(get_settings(), "site_rules", marked)
