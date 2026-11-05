from app.modules.plans.schemas import PlanJSON


def test_empty_plan_is_valid() -> None:
    plan = PlanJSON()
    assert plan.units == "m"
    assert plan.levels == []

