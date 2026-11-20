"""Record every solve_layout call a brief makes (program, plot and options), as JSON.

    uv --directory backend run python ../tools/floorplan_cases/solver_inputs.py CASE.txt OUT.json

Used to prove a brief that already worked still reaches the solver with exactly the same
inputs (the solver itself is time-limited and multi-threaded, so its output varies run to
run even on the same code).
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("TESTING", "1")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "backend"))


def record(text: str) -> list[dict]:
    from app.modules.ai.floorplan.pipeline.layout import engine
    from golden import plan_for

    calls: list[dict] = []
    real = engine.solve_layout

    def spy(program, plot, topo, **kw):
        calls.append({
            "program": program.model_dump(mode="json"),
            "plot": plot.model_dump(mode="json"),
            "topology": {"root": topo.root, "parent": topo.parent},
            "options": {k: v for k, v in kw.items() if k != "workers"},
        })
        return real(program, plot, topo, **kw)

    engine.solve_layout = spy
    try:
        res = plan_for(text)
    finally:
        engine.solve_layout = real
    return [{"status": res.status}, *calls]


if __name__ == "__main__":
    out = record(Path(sys.argv[1]).read_text().strip())
    Path(sys.argv[2]).write_text(json.dumps(out, indent=1, sort_keys=True))
    print(out[0], len(out) - 1, "solver calls")
