"""Per room and area of a PlanTo3D build: read type, read size, the size its label states,
built size, and the builder or kit used. Standard library only.

    /usr/bin/python3 tools/diag/rooms_report.py JOB_DIR [--md]

JOB_DIR holds plan.json and build_report.json (written by blender/gen.py since PATCHES 53).
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DIM = re.compile(
    r"""(\d+(?:\.\d+)?)\s*(?:'|ft|’)?\s*-?\s*(\d+(?:\.\d+)?)?\s*(?:"|in|”)?\s*[xX×*]\s*"""
    r"""(\d+(?:\.\d+)?)\s*(?:'|ft|’)?\s*-?\s*(\d+(?:\.\d+)?)?\s*(?:"|in|”)?"""
)


def label_size(label: str) -> tuple[float, float] | None:
    """Feet from a label such as 15'9"X12'4", 15' X 12' or 4.5 X 3.6 (metres)."""
    m = DIM.search(label or "")
    if not m:
        return None
    a, ai, b, bi = m.groups()
    if "'" in label or "’" in label or "ft" in label.lower():
        return (float(a) + float(ai or 0) / 12, float(b) + float(bi or 0) / 12)
    va, vb = float(a), float(b)
    if va < 30 and vb < 30 and not ai and not bi and "." in m.group(0):
        return (va / 0.3048, vb / 0.3048)  # metres
    return (va, vb)


def report(job: Path) -> list[dict]:
    plan = json.loads((job / "plan.json").read_text())
    built = json.loads((job / "build_report.json").read_text()) if (job / "build_report.json").exists() else {}
    items = defaultdict(list)
    for it in built.get("items", []):
        items[(it["floor"], it["room"])].append(f"{it['fn']} ({it['source']})")
    by_floor = defaultdict(list)  # gen.py reports the zones of a floor in the plan's order
    for z in built.get("zones", []):
        by_floor[z["floor"]].append(z)
    rows = []
    for k, f in enumerate(plan["floors"]):
        for i, r in enumerate(f["rooms"]):
            xs = [v for q in r["rects"] for v in (q[0], q[1])]
            ys = [v for q in r["rects"] for v in (q[2], q[3])]
            read = (round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1)) if xs else None
            area = round(sum((q[1] - q[0]) * (q[3] - q[2]) for q in r["rects"]), 1)
            lab = label_size(r.get("label", ""))
            z = by_floor[k][i] if i < len(by_floor[k]) else {}
            diff = None
            if lab and read:
                a, b = sorted(lab), sorted(read)
                diff = round(100 * max(abs(b[0] - a[0]) / a[0], abs(b[1] - a[1]) / a[1]), 1)
            rows.append(
                dict(
                    floor=k,
                    type=r["type"],
                    label=(r.get("label") or "")[:28],
                    read_ft=read,
                    read_area=area,
                    label_ft=tuple(round(v, 1) for v in lab) if lab else None,
                    label_diff_pct=diff,
                    built_area=z.get("built_area_ft2"),
                    water=z.get("water_size_ft"),
                    builder=z.get("builder", "?"),
                    items=", ".join(sorted(set(items.get((k, r.get("label") or r["type"]), [])))[:6]),
                )
            )
    return rows


def markdown(rows: list[dict]) -> str:
    out = [
        "| Type | Label | Read (ft) | Label says (ft) | Diff | Built area (ft²) | Builder | Furniture (source) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        built = r["built_area"] if r["built_area"] is not None else "-"
        if r["water"]:
            built = f"{built} (water {r['water'][0]} x {r['water'][1]})"
        said = f"{r['label_ft'][0]} x {r['label_ft'][1]}" if r["label_ft"] else ""
        diff = "" if r["label_diff_pct"] is None else f"{r['label_diff_pct']}%"
        read = f"{r['read_ft'][0]} x {r['read_ft'][1]} ({r['read_area']})" if r["read_ft"] else "-"
        out.append(
            f"| {r['type']} | {r['label']} | {read} | {said} | {diff} | {built} "
            f"| {r['builder']} | {r['items']} |"
        )
    return "\n".join(out)


if __name__ == "__main__":
    rows = report(Path(sys.argv[1]))
    print(markdown(rows) if "--md" in sys.argv else json.dumps(rows, indent=1))
