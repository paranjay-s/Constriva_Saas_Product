"""draw a plan JSON over its PDF page: python3 tools/dbg_plan.py plan.pdf plan.json out.png"""
import json, os, sys, random
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")]
import debug_draw, detect, vector  # noqa: E402

pdf, js, out = sys.argv[1:4]
P = json.load(open(js))
s = P["scale_pt_per_ft"]
layers = []
COL = dict(door=(0, 170, 0, 200), window=(0, 90, 255, 200), opening=(255, 200, 0, 220))
for f in P["floors"]:
    X0, Y1 = f["origin_pt"]
    R = lambda r: (X0 + r[0] * s, X0 + r[1] * s, Y1 - r[3] * s, Y1 - r[2] * s)
    random.seed(1)
    for rm in f["rooms"]:
        c = (random.randint(60, 230), random.randint(60, 230), random.randint(60, 230), 90)
        layers.append(("rect", [R(q) for q in rm["rects"]], c))
        q = R(rm["rects"][0])
        layers.append(("text", [(q[0] + 2, q[2] + 2, f'{rm["type"]} {rm["area"]:.0f}')], (0, 0, 0, 255)))
    layers.append(("rect", [R(w) for w in f["walls"] if not w[4]], (255, 0, 0, 170)))
    layers.append(("rect", [R(w) for w in f["walls"] if w[4]], (255, 0, 255, 170)))
    for t, c in COL.items():
        layers.append(("rect", [R(o["rect"]) for o in f["openings"] if o["type"] == t], c))
    layers.append(("rect", [R(st["rect"]) for st in f["stairs"]], (120, 60, 0, 120)))
    import furnish
    its = [i for i in furnish.furnish_floor(f) if i["box"][1] > i["box"][0]]
    layers.append(("rect", [R(i["box"]) for i in its], (40, 40, 40, 150)))
    layers.append(("text", [(R(i["box"])[0] + 1, (R(i["box"])[2] + R(i["box"])[3]) / 2, i["fn"][:6]) for i in its], (255, 255, 0, 255)))
if len(sys.argv) > 4:
    p = vector.read_page(pdf)
    layers.append(("circle", [(a[0], a[1], a[2]) for a in detect.arcs(p["curves"]) if a[2] < 60], (0, 160, 160, 255)))
debug_draw.draw(pdf, layers, out, dpi=130)
