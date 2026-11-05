"""Write the PlanJSON schema to shared/plan-schema/plan.schema.json."""

import json
from pathlib import Path

from app.modules.plans.schemas import PlanJSON

# backend/app/modules/plans/export_schema.py -> repository root is parents[4]
OUTPUT = Path(__file__).resolve().parents[4] / "shared" / "plan-schema" / "plan.schema.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(PlanJSON.model_json_schema(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()

