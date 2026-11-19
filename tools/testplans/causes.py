"""Why wall length is missed or extra: per plan and per style, from readings saved by score_all.py --dump.

    uv --directory backend run python ../tools/testplans/causes.py PLANS_DIR DUMP_DIR [--worst N]

Every unmatched sample (the scorer's 0.1 ft samples, openings neutral) is put in one cause by its nearest parallel
wall of the other plan, on the same storey:
  offset     a parallel wall runs alongside within 2 ft across: the wall is there, but its centre line is shifted
             (a thickness read as one face, a scale or frame error)
  short/long the wall's line is right (within tolerance across) but it stops short of, or runs past, the other's end
  absent     nothing parallel within 2 ft: a wall not read at all (missed) or one that is not there (extra)
  storey     the storey itself is missing from the reading (missed) or not in the truth (extra)
A plan-wide offset (the same shift for most walls) is reported separately as a frame error: the median signed
offset across all near walls, per axis.
"""

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services/planto3d/tools"))
import score_plan as sp  # noqa: E402

NEAR = 2.0  # ft


def classify(a, b, skip):
    """unmatched length of lines a against lines b, by cause; and the signed offsets of near walls"""
    out = defaultdict(float)
    shifts = {True: [], False: []}
    for h, c, a0, a1 in a:
        n = max(1, int((a1 - a0) / sp.STEP))
        step = (a1 - a0) / n
        for i in range(n):
            t = a0 + (i + 0.5) * step
            if any(h2 == h and abs(c2 - c) <= sp.TOL and s0 <= t <= s1 for h2, c2, s0, s1 in skip):
                continue
            par = [(c2 - c, b0, b1) for h2, c2, b0, b1 in b if h2 == h]
            if any(abs(d) <= sp.TOL and b0 - sp.TOL <= t <= b1 + sp.TOL for d, b0, b1 in par):
                continue  # matched
            along = [d for d, b0, b1 in par if abs(d) <= NEAR and b0 - sp.TOL <= t <= b1 + sp.TOL]
            if along:
                d = min(along, key=abs)
                out["offset"] += step
                shifts[h].append(d)
            elif any(abs(d) <= sp.TOL for d, _, _ in par):
                out["short/long"] += step
            else:
                out["absent"] += step
    return out, shifts


def main() -> None:
    plans, dump = Path(sys.argv[1]), Path(sys.argv[2])
    worst = int(sys.argv[sys.argv.index("--worst") + 1]) if "--worst" in sys.argv else 5
    index = [i for i in json.loads((plans / "index.json").read_text()) if i["held_out"]]
    per_style = defaultdict(lambda: defaultdict(float))
    rows = []
    for item in index:
        ref = json.loads((plans / f"{item['id']}.json").read_text())
        det = json.loads((dump / f"{item['id']}.det.json").read_text())
        miss, extra = defaultdict(float), defaultdict(float)
        shifts = {True: [], False: []}
        tot_r = tot_d = 0.0
        for k, rf in enumerate(ref["floors"]):
            df = det["floors"][k] if k < len(det.get("floors", [])) else None
            a = sp.centre_lines(rf)
            skip = sp.opening_spans(rf) + (sp.opening_spans(df) if df else [])
            tot_r += sp.matched_length(a, [], skip)[1]
            if df is None:
                miss["storey"] += sp.matched_length(a, [], skip)[1]
                continue
            b = sp.centre_lines(df)
            tot_d += sp.matched_length(b, [], skip)[1]
            m, s1 = classify(a, b, skip)
            e, _ = classify(b, a, skip)
            for key, v in m.items():
                miss[key] += v
            for key, v in e.items():
                extra[key] += v
            for h in (True, False):
                shifts[h] += s1[h]
        for df in det.get("floors", [])[len(ref["floors"]):]:
            b = sp.centre_lines(df)
            extra["storey"] += sp.matched_length(b, [], [])[1]
            tot_d += sp.matched_length(b, [], [])[1]
        frame = {("y" if h else "x"): round(statistics.median(v), 2) for h, v in shifts.items() if len(v) > 50}
        recall = 1 - sum(miss.values()) / tot_r if tot_r else 0
        prec = 1 - sum(extra.values()) / tot_d if tot_d else 0
        rows.append(dict(id=item["id"], style=item["style"], reader=det.get("_reader", "?"), recall=recall,
                         precision=prec, miss=dict(miss), extra=dict(extra), frame=frame, ref_ft=tot_r, det_ft=tot_d))
        g = per_style["vector" if not item["style"].startswith("raster") else "raster"]
        g2 = per_style[item["style"]]
        for gg in (g, g2):
            gg["ref"] += tot_r
            gg["det"] += tot_d
            for key, v in miss.items():
                gg["miss " + key] += v
            for key, v in extra.items():
                gg["extra " + key] += v

    keys = ["miss offset", "miss short/long", "miss absent", "miss storey",
            "extra offset", "extra short/long", "extra absent", "extra storey"]
    print("| group | " + " | ".join(keys) + " |")
    print("|---|" + "---|" * len(keys))
    for name in sorted(per_style, key=lambda n: (n not in ("vector", "raster"), n)):
        g = per_style[name]
        cells = [f"{100 * g[k] / (g['ref'] if k.startswith('miss') else g['det']):.0f}%" if g[k] else "-" for k in keys]
        print(f"| {name} | " + " | ".join(cells) + " |")
    print("\n(shares of truth length for missed, of read length for extra)\n")
    for group in ("vector", "raster"):
        rs = sorted((r for r in rows if r["style"].startswith("raster") == (group == "raster")),
                    key=lambda r: r["recall"] + r["precision"])[:worst]
        print(f"worst {group}:")
        for r in rs:
            m = ", ".join(f"{k} {v:.0f}" for k, v in sorted(r["miss"].items(), key=lambda kv: -kv[1]))
            e = ", ".join(f"{k} {v:.0f}" for k, v in sorted(r["extra"].items(), key=lambda kv: -kv[1]))
            print(f"  {r['id']} {r['style']:<15} {r['reader']:<8} recall {r['recall']:.2f} precision "
                  f"{r['precision']:.2f} frame {r['frame']} | missed ft: {m} | extra ft: {e}")
    Path(dump / "causes.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
