"""Score the readers on generated plans, per drawing style.

    uv --directory backend run python ../tools/testplans/score_all.py PLANS_DIR [--set held|tune|all] [--ai N]
           [--label NAME] [--out ../docs/overnight/accuracy.md]

Readers, in the gateway's order: PlanTo3D's detector (run with the user's python, /usr/bin/python3); when it refuses,
our AI plan reader, converted (only for up to N plans whose reply is not cached yet: live calls are budgeted; cached
replies are free and always used). A plan nothing reads scores zero. Lengths are pooled over plans (a plan with more
wall weighs more). Appends a section to the output file and prints it.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P3D = ROOT / "services/planto3d"
sys.path.insert(0, str(P3D / "tools"))
sys.path.insert(0, str(ROOT / "backend"))
import score_plan  # noqa: E402

CACHE = ROOT / "backend/.tmp/plan_cache"


def detect(pdf):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "plan.json"
        r = subprocess.run(["/usr/bin/python3", "detect.py", str(Path(pdf).resolve()), str(out)], cwd=P3D,
                           capture_output=True, text=True, timeout=300)
        return json.loads(out.read_text()) if r.returncode == 0 and out.exists() else None


def cached(pdf):
    h = hashlib.sha256(pdf.read_bytes()).hexdigest()
    return CACHE.is_dir() and any(CACHE.glob(f"{h}.parser-*"))


def ai_read(pdf):
    from app.modules.parsing.llm_parser import parse_plan_pdf
    from app.modules.plan3d.convert import planjson_to_planto3d
    try:
        res = planjson_to_planto3d(parse_plan_pdf(pdf.read_bytes(), min_rooms=1), source_name=pdf.name, reader="ai")
    except Exception as e:  # noqa: BLE001 - any failure is a plan nothing could read
        print(f"  ai failed on {pdf.name}: {type(e).__name__}", file=sys.stderr)
        return None
    return res.plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plans")
    ap.add_argument("--set", default="held", choices=["held", "tune", "all"])
    ap.add_argument("--ai", type=int, default=0, help="most fresh AI calls")
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--out", default=str(ROOT / "docs/overnight/accuracy.md"))
    a = ap.parse_args()
    d = Path(a.plans)
    index = json.loads((d / "index.json").read_text())
    pick = [i for i in index if a.set == "all" or i["held_out"] == (a.set == "held")]
    agg = defaultdict(lambda: defaultdict(float))
    fresh = 0
    for item in pick:
        pdf, ref = d / f"{item['id']}.pdf", json.loads((d / f"{item['id']}.json").read_text())
        det, reader = detect(pdf), "detector"
        if det is None:
            reader = "ai"
            if cached(pdf):
                det = ai_read(pdf)
            elif fresh < a.ai:
                fresh += 1
                det = ai_read(pdf)
            else:
                reader = "none"
        det = det or {"floors": []}
        s = score_plan.plan_score(det, ref)
        for key in (item["style"], "ALL"):
            g = agg[key]
            g["plans"] += 1
            g["read"] += reader != "none" and bool(det["floors"])
            g["by_" + reader] += 1
            for r in s["floors"]:
                for f in ("hit_r", "len_r", "hit_d", "len_d", "n_rooms", "rooms_found", "types_ok",
                          "doors_found", "doors_ref", "windows_found", "windows_ref"):
                    g[f] += r.get(f, 0) or 0
            if not s["floors"]:
                for k in ref["floors"]:
                    g["len_r"] += sum(max(w[1] - w[0], w[3] - w[2]) for w in k["walls"])
            g["storeys_ok"] += s["storeys_ok"]
            g["kind_ok"] += s["kind_ok"]
            g["specials_found"] += s["specials_found"]
            g["specials_total"] += s["specials_total"]
        print(f"{item['id']} {item['style']:<16} {reader:<8} recall {sum(r['hit_r'] for r in s['floors']) / max(1e-9, sum(r['len_r'] for r in s['floors'])) if s['floors'] else 0:.2f}", flush=True)

    pct = lambda n, t: f"{100 * n / t:.0f}%" if t else "-"
    lines = [f"\n## {a.label} ({a.set} set, {len(pick)} plans, {fresh} fresh AI calls)\n",
             "| style | plans | read | detector / ai / none | wall recall | wall precision | doors found | windows found | room type | specials | storeys |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for key in sorted(agg, key=lambda k: (k == "ALL", k)):
        g = agg[key]
        lines.append(f"| {key} | {g['plans']:.0f} | {pct(g['read'], g['plans'])} | {g['by_detector']:.0f} / {g['by_ai']:.0f} / {g['by_none']:.0f} | "
                     f"{pct(g['hit_r'], g['len_r'])} | {pct(g['hit_d'], g['len_d'])} | {pct(g['doors_found'], g['doors_ref'])} | "
                     f"{pct(g['windows_found'], g['windows_ref'])} | {pct(g['types_ok'], g['n_rooms'])} | "
                     f"{pct(g['specials_found'], g['specials_total'])} | {pct(g['storeys_ok'], g['plans'])} |")
    text = "\n".join(lines) + "\n"
    print(text)
    with open(a.out, "a", encoding="utf-8") as fh:
        fh.write(text)


if __name__ == "__main__":
    main()
