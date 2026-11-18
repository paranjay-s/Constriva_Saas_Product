"""Draw examples/sample_plan.pdf: a made-up single-storey house in the style of a CAD export (double-line walls,
door swings, window glass lines, room names with sizes). It is the demo input and the fixture of tests/test_sample.py.
python3 examples/make_sample.py        (standard library only; sizes in feet, 12 pt per foot on an A4 landscape sheet)"""
import math, os

S, OX, OY = 12.0, 205.0, 150.0                    # points per foot, sheet position of the plan's lower-left corner
T, U = 0.75, 0.5                                  # outer / inner wall thickness
# wall runs (x0, x1, y0, y1) and the openings cut into them (kind, from, to, swing side) along their length
WALLS = [
    ((0, 36, 0, T), [("door", 9, 12.5, 1), ("window", 16.5, 20.5, 0)]),                # bottom
    ((0, 36, 28 - T, 28), [("window", 13.75, 15.75, 0), ("window", 28, 33, 0)]),       # top
    ((0, T, 0, 28), [("window", 22, 26, 0)]),                                          # left
    ((36 - T, 36, 0, 28), [("window", 9.5, 13.5, 0)]),                                 # right
    ((T, 36 - T, 14.75, 15.25), [("door", 8, 11, 1), ("door", 13.5, 16, 1), ("door", 18.75, 21.75, 1)]),
    ((22.75, 23.25, T, 14.75), [("door", 2, 5, 1)]),                                   # living | kitchen
    ((11.75, 12.25, 15.25, 28 - T), []),                                               # bedroom | toilet
    ((17.25, 17.75, 15.25, 28 - T), []),                                               # toilet | bedroom
]
ROOMS = [("LIVING", "22'x14'", 11.75, 8.3), ("KITCHEN", "12'x14'", 29.25, 8.3), ("BEDROOM", "11'x12'", 6.25, 21.8),
         ("TOILET", "5'x12'", 14.75, 21.8), ("BEDROOM", "17'6x12'", 26.5, 21.8)]
EXPECT = dict(size=(36, 28), doors=5, windows=5, rooms=["bedroom", "bedroom", "kitchen", "living", "toilet"])

out = []
P = lambda x, y: (OX + x * S, OY + y * S)
pen = lambda width, grey: out.append(f"{width} w {grey} G")
line = lambda x0, y0, x1, y1: out.append("%.2f %.2f m %.2f %.2f l S" % (*P(x0, y0), *P(x1, y1)))
rect = lambda x0, x1, y0, y1: out.append("%.2f %.2f %.2f %.2f re S" % (*P(x0, y0), (x1 - x0) * S, (y1 - y0) * S))


def text(x, y, s, size=8.0):                      # centred on x (Helvetica: about 0.56 em per character)
    px, py = P(x, y)
    out.append("BT /F1 %.1f Tf %.2f %.2f Td (%s) Tj ET" % (size, px - 0.28 * size * len(s), py, s))


def swing(hx, hy, r, a0):                         # quarter circle from angle a0 to a0 + 90 deg around the hinge
    k, a1 = 0.5523 * r, a0 + math.pi / 2
    p0 = (hx + r * math.cos(a0), hy + r * math.sin(a0))
    p3 = (hx + r * math.cos(a1), hy + r * math.sin(a1))
    c1 = (p0[0] - k * math.sin(a0), p0[1] + k * math.cos(a0))
    c2 = (p3[0] + k * math.sin(a1), p3[1] - k * math.cos(a1))
    out.append("%.2f %.2f m %.2f %.2f %.2f %.2f %.2f %.2f c S" % (*P(*p0), *P(*c1), *P(*c2), *P(*p3)))
    line(hx, hy, *p3)                             # the door leaf, standing open


for (x0, x1, y0, y1), cuts in WALLS:
    horiz = x1 - x0 > y1 - y0
    a, b = (x0, x1) if horiz else (y0, y1)
    pen(0.9, 0)                                   # walls: the heaviest pen
    for p0, p1 in zip([a] + [c[2] for c in cuts], [c[1] for c in cuts] + [b]):
        rect(p0, p1, y0, y1) if horiz else rect(x0, x1, p0, p1)
    pen(0.3, 0.25)
    for kind, c0, c1, side in cuts:
        if kind == "window":                      # frame and glass lines inside the wall, jamb to jamb
            for f in (0.25, 0.5, 0.75):
                line(c0, y0 + f * (y1 - y0), c1, y0 + f * (y1 - y0)) if horiz else line(x0 + f * (x1 - x0), c0, x0 + f * (x1 - x0), c1)
        elif horiz:                               # door: hinged at the gap's low end, opening towards +y
            swing(c0, y1, c1 - c0, 0)
        else:
            swing(x1, c0, c1 - c0, 0)
pen(0.25, 0.78)                                   # pale pen: floor tiles and furniture (the detector ignores pale lines)
for k in range(1, 5):
    line(12.25 + k, 15.25, 12.25 + k, 27.25)
for k in range(1, 12):
    line(12.25, 15.25 + k, 17.25, 15.25 + k)
for x0, x1, y0, y1 in ((1.2, 7.7, 20.2, 26.8), (1.5, 4.3, 24.6, 26.4), (4.6, 7.4, 24.6, 26.4),         # bed, pillows
                       (27.5, 34.8, 19.5, 26.8), (28, 31, 24.6, 26.4), (31.4, 34.4, 24.6, 26.4),
                       (1.2, 4.2, 1.5, 4.5), (4.4, 12.4, 10.5, 13.5), (5.4, 11.4, 5.5, 8.5),             # chair, sofa, table
                       (33.2, 35.25, 0.75, 9), (23.25, 33.2, 12.7, 14.75), (25, 27.5, 13.1, 14.4),       # counters, sink
                       (12.6, 14.4, 25, 27), (15.2, 17, 24.8, 26.8), (12.6, 14.2, 15.6, 17.6)):          # wc, basin, shower
    rect(x0, x1, y0, y1)
pen(0.3, 0.25)                                    # sheet border, title box, overall sizes
out.append("20 20 802 555 re S")
out.append("600 28 214 64 re S")
for x0, y0, x1, y1 in ((0, -2.5, 36, -2.5), (0, -3, 0, -2), (36, -3, 36, -2), (-2.5, 0, -2.5, 28), (-3, 0, -2, 0), (-3, 28, -2, 28)):
    line(x0, y0, x1, y1)
out.append("0 g")
for name, size, x, y in ROOMS:
    text(x, y, name)
    text(x, y - 1.1, size, 7.0)
text(18, -5.2, "GROUND FLOOR PLAN", 12.0)
out.append("BT /F1 11 Tf 614 66 Td (SAMPLE HOUSE) Tj ET")
out.append("BT /F1 8 Tf 614 46 Td (PlanTo3D example drawing) Tj ET")

stream = "\n".join(out).encode()
objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
pdf, offs = b"%PDF-1.4\n", []
for i, o in enumerate(objs, 1):
    offs.append(len(pdf))
    pdf += b"%d 0 obj\n" % i + o + b"\nendobj\n"
xref = len(pdf)
pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
if __name__ == "__main__":
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_plan.pdf")
    open(path, "wb").write(pdf)
    print("wrote", path)
