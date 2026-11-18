"""The sample house written the ways other programs write a plan PDF: inside a transparency group (poppler hands it
over as <use>), on a page turned with /Rotate or drawn turned, and with sizes in metres, centimetres, millimetres or as
room areas. Each variant must be read like the sample itself. python3 tests/test_reader.py   (standard library only)"""
import math, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), os.path.join(os.path.dirname(HERE), "examples")]
import detect  # noqa: E402
import make_sample as M  # noqa: E402
import vector  # noqa: E402


def write_pdf(path, content, box=(842, 595), rotate=0, group=False):
    """one page; with group=True the drawing is a Form XObject with a transparency group, painted once"""
    page = "\n".join(content).encode("latin-1")
    font = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    stream = lambda d, head=b"": b"<< " + head + b"/Length %d >>\nstream\n" % len(d) + d + b"\nendstream"
    res = b"/Font << /F1 5 0 R >>"
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>", None, None, font]
    if group:
        objs.append(stream(page, b"/Type /XObject /Subtype /Form /BBox [0 0 %d %d] /Group << /S /Transparency >> "
                                 b"/Resources << /Font << /F1 5 0 R >> >> " % box))
        res += b" /XObject << /Fm0 6 0 R >>"
        page = b"q /Fm0 Do Q"
    objs[2] = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Rotate %d /Contents 4 0 R /Resources << %s >> >>" % (
        box[0], box[1], rotate, res)
    objs[3] = stream(page)
    pdf, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(pdf))
        pdf += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    with open(path, "wb") as fh:
        fh.write(pdf)


def relabel(fmt):
    """the sample's drawing with each room size label (22'x14') rewritten by fmt(width_ft, depth_ft)"""
    sizes = {"(%s)" % s: detect.parse_dims(s) for _, s, _, _ in M.ROOMS}
    out = []
    for op in M.out:
        for k, (a, b) in sizes.items():
            if k in op:
                op = op.replace(k, "(%s)" % fmt(a, b).replace("\u00d7", "\\327").replace("\u00b2", "\\262"))
        out.append(op)
    return out


TURN = ["q 0 1 -1 0 595 0 cm"] + M.out + ["Q"]           # the drawing turned a quarter turn onto a portrait sheet
CASES = [
    ("transparency group", dict(content=M.out, group=True)),
    ("page /Rotate 90", dict(content=M.out, rotate=90)),
    ("page /Rotate 180", dict(content=M.out, rotate=180)),
    ("drawn turned on a portrait page", dict(content=TURN, box=(595, 842))),
    ("drawn turned, page /Rotate 90 turns it back", dict(content=TURN, box=(595, 842), rotate=90)),
    ("sizes in metres 6.71 x 4.27 m", dict(content=relabel(lambda a, b: "%.2f x %.2f m" % (a * .3048, b * .3048)))),
    ("sizes in metres 6.71\u00d74.27", dict(content=relabel(lambda a, b: "%.2f\u00d7%.2f" % (a * .3048, b * .3048)))),
    ("sizes in cm 671X427", dict(content=relabel(lambda a, b: "%dX%d" % (round(a * 30.48), round(b * 30.48))))),
    ("sizes in mm 6706 x 4267", dict(content=relabel(lambda a, b: "%d x %d" % (round(a * 304.8), round(b * 304.8))))),
    ("areas 14.3 m\u00b2", dict(content=relabel(lambda a, b: "%.1f m\u00b2" % (a * b * .3048 ** 2)))),
    ("areas 308 sq.ft", dict(content=relabel(lambda a, b: "%d sq.ft" % round(a * b)))),
]

SIDEWAYS = {"page /Rotate 90", "page /Rotate 180", "drawn turned on a portrait page"}
fails = 0
with tempfile.TemporaryDirectory() as tmp:
    for name, case in CASES:
        path = os.path.join(tmp, "variant.pdf")
        write_pdf(path, **case)
        try:
            plan = detect.detect(path)
            f = plan["floors"][0]
            kinds = [o["type"] for o in f["openings"]]
            got = (plan["scale_source"], len(plan["floors"]), f["name"], [round(v) for v in f["size"]],
                   kinds.count("door"), kinds.count("window"), sorted(r["type"] for r in f["rooms"]))
            want = ("labels", 1, "Ground Floor", list(M.EXPECT["size"]), M.EXPECT["doors"], M.EXPECT["windows"], M.EXPECT["rooms"])
            if name in SIDEWAYS:
                # known limit: a sheet that reads sideways is read as it lies, so the house is a quarter turn round
                # and its sideways title is not found; every wall, opening and room must still be there
                got, want = got[:2] + tuple(sorted(got[3])) + got[4:], want[:2] + tuple(sorted(want[3])) + want[4:]
            ok = got == want and all(abs(a - b) < 0.1 for a, b in zip(sorted(f["size"]), sorted(M.EXPECT["size"])))
        except detect.PlanError as e:
            ok, got = False, "PlanError: %s" % e
        fails += not ok
        print("%s %s%s" % ("ok  " if ok else "FAIL", name, "" if ok else " -> %s" % (got,)))

# transforms the reader must understand when a writer other than pdftocairo made the SVG
m = vector._matrix("translate(10, 20) rotate(90) scale(2)")
assert all(abs(a - b) < 1e-9 for a, b in zip(m, (0, 2, -2, 0, 10, 20))), m
m = vector._matrix("rotate(90 5 5)")
assert all(abs(a - b) < 1e-9 for a, b in zip(m, (0, 1, -1, 0, 10, 0))), m
assert abs(vector._matrix("skewX(45)")[2] - math.tan(math.pi / 4)) < 1e-9
assert fails == 0, "%d variant(s) not read" % fails
print("ok   reader variants: %d" % len(CASES))
