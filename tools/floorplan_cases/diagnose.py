"""Why does a brief fail? Re-solve its recorded program with one family of constraints
removed at a time (replay only: no live AI calls).

    uv --directory backend run python ../tools/floorplan_cases/diagnose.py CASE.txt [--time 20]
"""

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("TESTING", "1")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm_cache import RecordingLLM  # noqa: E402


def main() -> None:
    args = sys.argv[1:]
    limit = float(args[args.index("--time") + 1]) if "--time" in args else 20.0
    from app.modules.ai.floorplan.pipeline.brief_parser import parse_brief
    from app.modules.ai.floorplan.pipeline.generate import (
        meta_from_brief, plot_from_brief, with_daylight, built_up_target)
    from app.modules.ai.floorplan.pipeline.layout.solver import solve_layout
    from app.modules.ai.floorplan.pipeline.layout.topology import build_topology
    from app.modules.ai.floorplan.pipeline.layout.engine import with_spare_garden
    from app.modules.ai.floorplan.pipeline.room_program import build_program
    from app.modules.ai.floorplan.schemas.brief import BriefForm
    from app.modules.ai.floorplan.schemas.plan import Setbacks

    llm = RecordingLLM(ROOT / "backend/tests/floorplan/fixtures/llm_cache")
    brief = parse_brief(BriefForm(prompt=Path(args[0]).read_text().strip()), llm).brief
    plot = plot_from_brief(brief)
    prog, _ = build_program(brief, llm)
    prog = with_spare_garden(prog, plot)
    plot_m2 = plot.width * plot.depth / 1e4
    enclosed = sum(r.target_area_m2 for r in prog.rooms if r.zone != "open")
    openm2 = sum(r.target_area_m2 for r in prog.rooms if r.zone == "open")
    x0, y0, x1, y1 = plot.buildable()
    print(f"plot {plot.width}x{plot.depth} cm = {plot_m2:.0f} m2; buildable "
          f"{(x1-x0)*(y1-y0)/1e4:.0f} m2; built-up target {plot.built_up_m2}; "
          f"brief built_up_m2={brief.plot.built_up_m2} share={brief.built_up_share}")
    print(f"program: {len(prog.rooms)} rooms, enclosed {enclosed:.0f} m2, open {openm2:.0f} m2, "
          f"sum {enclosed + openm2:.0f} m2; rules {len(prog.rules)}; adjacency {len(prog.adjacency)}")
    for r in prog.rules:
        print("   rule:", r.model_dump(exclude={'text'}))

    def run(name, program, plot_):
        topo = build_topology(program)
        t0 = time.time()
        rooms = solve_layout(program, plot_, topo, time_limit_s=limit, seed=0, workers=8)
        print(f"{name:42s} {'FOUND' if rooms else 'none '} {time.time() - t0:5.1f}s", flush=True)
        return rooms

    nosb = plot.model_copy(update={"setbacks": Setbacks()})
    run("as generated (no daylight rules)", prog, plot)
    run("with daylight for every habitable room", with_daylight(prog), plot)
    run("no rules", prog.model_copy(update={"rules": []}), plot)
    run("no setbacks", prog, nosb)
    run("no rules, no setbacks", prog.model_copy(update={"rules": []}), nosb)
    kinds = sorted({r.kind for r in prog.rules})
    for k in kinds:
        run(f"without '{k}' rules", prog.model_copy(
            update={"rules": [r for r in prog.rules if r.kind != k]}), plot)
    run("no adjacency wishes", prog.model_copy(update={"adjacency": []}), plot)
    small = prog.model_copy(update={"rooms": [
        r.model_copy(update={"target_area_m2": r.target_area_m2 * 0.8}) for r in prog.rooms]})
    run("rooms at 80%", small, plot)


if __name__ == "__main__":
    main()
