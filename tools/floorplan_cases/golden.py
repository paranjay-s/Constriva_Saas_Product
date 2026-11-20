"""Write the plan a brief makes (replayed AI answers) as JSON, for golden comparisons.

    uv --directory backend run python ../tools/floorplan_cases/golden.py CASE.txt OUT.json
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("TESTING", "1")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm_cache import RecordingLLM  # noqa: E402


def plan_for(text: str):
    from app.modules.ai.floorplan.pipeline.brief_parser import parse_brief
    from app.modules.ai.floorplan.pipeline.generate import generate_plan
    from app.modules.ai.floorplan.schemas.brief import BriefForm

    llm = RecordingLLM(ROOT / "backend/tests/floorplan/fixtures/llm_cache")
    brief = parse_brief(BriefForm(prompt=text), llm).brief
    return generate_plan(brief, llm=llm, plan_id="golden")


if __name__ == "__main__":
    res = plan_for(Path(sys.argv[1]).read_text().strip())
    data = json.dumps(res.plan.model_dump(mode="json"), indent=1, sort_keys=True)
    Path(sys.argv[2]).write_text(data)
    print(res.status, res.method, res.attempts)
