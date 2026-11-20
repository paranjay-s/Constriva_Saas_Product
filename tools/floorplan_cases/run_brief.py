"""Run a typed or spoken brief through the generator, with the AI answers recorded.

    uv --directory backend run python ../tools/floorplan_cases/run_brief.py CASE.txt [--live]
        [--cache DIR] [--out DIR]

Prints the parsed brief, the attempts and the result. Without --live only cached AI answers are
used (an uncached call fails as if the AI were down).
"""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm_cache import RecordingLLM  # noqa: E402


def main() -> None:
    args = sys.argv[1:]
    live = "--live" in args
    cache = Path(args[args.index("--cache") + 1]) if "--cache" in args else (
        ROOT / "backend/tests/floorplan/fixtures/llm_cache")
    text = Path(args[0]).read_text().strip()
    if not live:
        os.environ.setdefault("TESTING", "1")
    from app.modules.ai.floorplan.pipeline.brief_parser import parse_brief
    from app.modules.ai.floorplan.pipeline.generate import generate_plan
    from app.modules.ai.floorplan.schemas.brief import BriefForm
    from app.modules.ai.floorplan.service import describe

    inner = None
    if live:
        from app.modules.ai.llm.neutral import get_generator_llm

        inner = get_generator_llm()
        print("model:", getattr(inner, "provider", "?"), getattr(inner, "model", "?"))
    llm = RecordingLLM(cache, inner, live=live)
    res = parse_brief(BriefForm(prompt=text), llm)
    b = res.brief
    print("SUMMARY:", describe(b))
    print("MISSING:", res.missing, "WARN:", res.warnings)
    print("BRIEF:", json.dumps(b.model_dump(mode="json"), indent=None)[:3000])
    if res.missing:
        return
    t0 = time.time()
    g = generate_plan(b, llm=llm)
    print("STATUS:", g.status, f"{time.time() - t0:.1f}s")
    print("MESSAGE:", g.message)
    print("ATTEMPTS:", g.attempts)
    print("WARNINGS:", g.warnings)
    if g.feasibility:
        print("FEAS:", g.feasibility.message, g.feasibility.options)
    if g.program:
        print("PROGRAM:", json.dumps(g.program.model_dump(mode="json"))[:4000])
    print(f"LLM live calls {llm.calls}, cache hits {llm.hits}")


if __name__ == "__main__":
    main()
