"""The eval set stays well-formed: every form is valid and every expectation is known."""

import importlib.util
from pathlib import Path

import pytest

from app.modules.ai.floorplan.schemas.brief import BriefForm
from app.modules.ai.floorplan.schemas.common import RoomType

RUN_EVAL = Path(__file__).resolve().parents[2] / "eval" / "floorplan" / "run_eval.py"
spec = importlib.util.spec_from_file_location("run_eval", RUN_EVAL)
run_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_eval)

CASES = run_eval.load_cases()
ROOM_TYPES = set(RoomType.__args__)


def test_eval_set_size_and_unique_ids() -> None:
    ids = [c["id"] for c in CASES]
    assert 30 <= len(ids) <= 50
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case_is_well_formed(case: dict) -> None:
    BriefForm.model_validate(case["form"])
    assert set(case["expect"]) <= run_eval.EXPECT_KEYS
    for t in case["expect"].get("has", []):
        assert t in ROOM_TYPES
    for pair in case["expect"].get("adjacent", []):
        assert len(pair) == 2 and set(pair) <= ROOM_TYPES


@pytest.mark.parametrize("case", [c for c in CASES if c["id"] in ("f01_2bhk_form_only",)])
def test_form_only_case_passes(case: dict) -> None:
    result = run_eval.run_case(case, llm=None)
    assert result["passed"], result
