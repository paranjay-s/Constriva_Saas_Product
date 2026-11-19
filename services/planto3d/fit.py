"""Rooms sized to their labels. plan -> plan (in place), report.

Every room edge lies on a wall line. Per axis, the distinct lines (within TOL) are the unknowns. Each room whose label
gives its size and whose drawn size is within LIMIT of it adds one equation per axis: its far line minus its near line
equals the labelled size (clear size between wall faces, or the centre-line size, whichever the drawing is closer
to). A weak pull keeps every line near where it was drawn, so unlabelled parts stay put. The least-squares solution
moves the lines; walls, openings, stairs, rooms and labels are remapped piecewise-linearly between the lines, so shared
walls move together and nothing crosses. Rooms further off than LIMIT are reported, not forced.
Standard library only."""

TOL = 0.1           # ft: edges this close are one line (less than any wall is thick: a wall's faces stay apart)
LIMIT = 0.10        # rooms more than 10 % off their label are reported, not fitted
PULL = 0.05         # weight of "stay where drawn" against 1.0 for "match the label"
THICK = 5.0         # weight of "a wall keeps its thickness"


def _lines(vals):
    """sorted distinct values (clusters within TOL) -> list of cluster centres"""
    out = []
    for v in sorted(vals):
        if out and v - out[-1][-1] <= TOL:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(c) / len(c) for c in out]


def _index(lines, v):
    k = min(range(len(lines)), key=lambda i: abs(lines[i] - v))
    return k if abs(lines[k] - v) <= TOL else None


def _solve(A, b):
    """least squares by the normal equations (small systems): x = (A^T A)^-1 A^T b, Gauss-Jordan with pivoting"""
    n = len(A[0])
    M = [[sum(A[r][i] * A[r][j] for r in range(len(A))) for j in range(n)] + [sum(A[r][i] * b[r] for r in range(len(A)))]
         for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12:
            continue
        M[c], M[p] = M[p], M[c]
        pv = M[c][c]
        M[c] = [v / pv for v in M[c]]
        for r in range(n):
            if r != c and M[r][c]:
                f = M[r][c]
                M[r] = [a - f * bb for a, bb in zip(M[r], M[c])]
    return [M[i][n] for i in range(n)]


def _remap(old, new):
    """piecewise-linear map from the old line positions to the new ones (beyond the ends: shifted like the end)"""
    pts = sorted(zip(old, new))

    def f(v):
        if v <= pts[0][0]:
            return v + pts[0][1] - pts[0][0]
        if v >= pts[-1][0]:
            return v + pts[-1][1] - pts[-1][0]
        for (a0, b0), (a1, b1) in zip(pts, pts[1:]):
            if a0 <= v <= a1:
                t = (v - a0) / (a1 - a0) if a1 > a0 else 0.0
                return b0 + t * (b1 - b0)
        return v
    return f


def _scale_all(f, k):
    """every coordinate of the storey times k (about the origin)"""
    s = lambda q: [round(v * k, 3) for v in q[:4]] + list(q[4:])
    f["walls"] = [s(w) for w in f.get("walls", [])]
    for o in f.get("openings", []):
        o["rect"] = s(o["rect"])
        if o.get("hinge"):
            o["hinge"] = [round(v * k, 3) for v in o["hinge"]]
    for st in f.get("stairs", []):
        st["rect"] = s(st["rect"])
    for r in f.get("rooms", []):
        r["rects"] = [s(q) for q in r.get("rects", [])]


def scale_ratio(rooms, wall):
    """label / drawn for every labelled room and axis (the orientation and size convention that fit best) -> the
    median when the rooms agree on it (half of them within 3 % of it), else None"""
    ratios = []
    for r in rooms:
        q = r["rects"][0]
        w_, h_ = q[1] - q[0], q[3] - q[2]
        a, b = r["dims"]
        best = min(((la, lb, c) for la, lb in ((a, b), (b, a)) for c in (0.0, wall)),
                   key=lambda t: abs(w_ + t[2] - t[0]) / t[0] + abs(h_ + t[2] - t[1]) / t[1])
        la, lb, c = best
        if max(abs(w_ + c - la) / la, abs(h_ + c - lb) / lb) <= LIMIT:
            ratios += [(la - c) / w_, (lb - c) / h_]
    if len(ratios) < 4:
        return None
    ratios.sort()
    med = ratios[len(ratios) // 2]
    return med if sum(abs(x - med) <= 0.03 * med for x in ratios) >= len(ratios) / 2 else None


def fit_floor(f, wall=0.5):
    """fit one storey's rooms to their labels -> report dict"""
    rooms = [r for r in f.get("rooms", []) if len(r.get("rects") or []) == 1 and r.get("dims")]
    rep = dict(fitted=[], reported=[], before=[], after=[], scale=1.0)
    if not rooms:
        return rep
    rep["before"] = [_off(r, wall) for r in rooms]
    # the plan's scale against all the labels together: a consistent small error is the scale, not the rooms
    k = scale_ratio(rooms, wall)
    if k and 0.005 < abs(k - 1) < 0.08:
        _scale_all(f, k)
        rep["scale"] = round(k, 4)
    walls = [w for w in f.get("walls", []) if len(w) >= 4]
    ok = []
    for r in rooms:
        q = r["rects"][0]
        w_, h_ = q[1] - q[0], q[3] - q[2]
        a, b = r["dims"]
        # the label's two sizes in the orientation that fits best, as clear or as centre-line sizes
        best = None
        for (la, lb) in ((a, b), (b, a)):
            for centre in (0.0, wall):
                ex, ey = abs(w_ + centre - la) / la, abs(h_ + centre - lb) / lb
                if best is None or ex + ey < best[0]:
                    best = (ex + ey, la - centre, lb - centre, max(ex, ey))
        err, tw, th, worst = best
        if worst > LIMIT:
            rep["reported"].append(dict(label=r.get("label"), drawn=[round(w_, 2), round(h_, 2)], label_size=[a, b], off=round(worst, 3)))
        elif worst > 0.002:
            ok.append((r, tw, th))
    if not ok:
        rep["after"] = [_off(r, wall) for r in rooms]
        return rep
    maps = []
    for axis, (lo_i, hi_i, size_i) in ((0, (0, 1, 1)), (1, (2, 3, 2))):
        vals = [w[k] for w in walls for k in (lo_i, hi_i)] + [r["rects"][0][k] for r in f["rooms"] for k in (lo_i, hi_i) if r.get("rects")]
        lines = _lines(vals)
        n = len(lines)
        A, bvec = [], []
        for r, tw, th in ok:
            q = r["rects"][0]
            i, j = _index(lines, q[lo_i]), _index(lines, q[hi_i])
            if i is None or j is None or i == j:
                continue
            row = [0.0] * n
            row[i], row[j] = -1.0, 1.0
            A.append(row)
            bvec.append(tw if axis == 0 else th)
        # a wall keeps its thickness: its two faces move together (strongly)
        for w in walls:
            if (w[1] - w[0] < w[3] - w[2]) != (axis == 0):
                continue                       # only walls that cross this axis have their faces on it
            i, j = _index(lines, w[lo_i]), _index(lines, w[hi_i])
            if i is None or j is None or i == j:
                continue
            row = [0.0] * n
            row[i], row[j] = -THICK, THICK
            A.append(row)
            bvec.append(THICK * (lines[j] - lines[i]))
        for k in range(n):
            row = [0.0] * n
            row[k] = PULL
            A.append(row)
            bvec.append(PULL * lines[k])
        new = _solve(A, bvec) if A else lines
        # keep the order of the lines (a fit never folds walls over each other)
        for k in range(1, n):
            new[k] = max(new[k], new[k - 1] + 0.05)
        maps.append(_remap(lines, new))
    fx, fy = maps

    def rect(q):
        return [round(fx(q[0]), 3), round(fx(q[1]), 3), round(fy(q[2]), 3), round(fy(q[3]), 3)]
    f["walls"] = [rect(w) + list(w[4:]) for w in walls]
    for o in f.get("openings", []):
        o["rect"] = rect(o["rect"])
        if o.get("hinge"):
            o["hinge"] = [round(fx(o["hinge"][0]), 3), round(fy(o["hinge"][1]), 3)]
    for s in f.get("stairs", []):
        s["rect"] = rect(s["rect"])
    for r in f.get("rooms", []):
        r["rects"] = [rect(q) for q in r.get("rects", [])]
        if r.get("rects"):
            r["area"] = round(sum((q[1] - q[0]) * (q[3] - q[2]) for q in r["rects"]), 1)
    for r, tw, th in ok:
        q = r["rects"][0]
        rep["fitted"].append(r.get("label"))
    rep["after"] = [_off(r, wall) for r in rooms]
    return rep


def _off(r, wall):
    """how far a room is from its label: the larger relative error of its two sides, best orientation and convention"""
    q = r["rects"][0]
    a, b = r["dims"]
    w_, h_ = q[1] - q[0], q[3] - q[2]
    return min(max(abs(w_ + c - la) / la, abs(h_ + c - lb) / lb) for la, lb in ((a, b), (b, a)) for c in (0.0, wall))


def fit_plan(plan):
    """fit every storey; -> {floors: [...], fitted, reported}. Rooms are marked size_source "label" when fitted"""
    wall = (plan.get("wall_pt") or 0) / (plan.get("scale_pt_per_ft") or 1) if plan.get("wall_pt") else 0.5
    reps = [fit_floor(f, wall) for f in plan.get("floors", [])]
    for f, rep in zip(plan.get("floors", []), reps):
        for r in f.get("rooms", []):
            if r.get("label") in rep["fitted"]:
                r["size_source"] = "label"
    plan["size_fit"] = dict(fitted=sum(len(r["fitted"]) for r in reps), reported=[x for r in reps for x in r["reported"]])
    return plan["size_fit"], reps
