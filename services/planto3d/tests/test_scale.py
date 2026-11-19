"""The scale from room-size labels (detect._scale_from_sizes, half_wall_share), on synthetic walls: no PDF.

A row of rooms, each labelled with its clear size in feet, drawn at S points per foot with 9" outer walls and 4.5"
partitions. Checks: a label ray through a door gap still finds the room's wall; a missing partition spoils the width
but the depths still give the scale; the clear reading is taken when its labels agree; 9" walls are recognised.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import detect  # noqa: E402

S = 5.0                     # points per foot
EXT, INT = 0.75 * S, 0.375 * S


def row(widths, depth, partitions=True, door_on_ray=False):
    """walls (x0, x1, y0, y1) in points and labels for rooms side by side; clear sizes in feet"""
    walls, labels = [], []
    x = 0.0
    xs = [x]
    for k, w in enumerate(widths):
        x += (EXT if k == 0 else INT) + w * S
        xs.append(x)
    total = x + EXT
    top, bottom = 0.0, EXT + depth * S + EXT
    walls += [(0, total, top, top + EXT), (0, total, bottom - EXT, bottom)]        # outer walls, top and bottom
    cy = (top + bottom) / 2
    for k, xe in enumerate(xs):
        t = EXT if k in (0, len(xs) - 1) else INT
        x0 = xe if k == 0 else xe
        if k not in (0, len(xs) - 1) and not partitions:
            continue
        if door_on_ray:          # a door across the label's line: the wall is two pieces
            walls += [(x0, x0 + t, top, cy - 1.5 * S), (x0, x0 + t, cy + 1.5 * S, bottom)]
        else:
            walls.append((x0, x0 + t, top, bottom))
    for k, w in enumerate(widths):
        x0 = xs[k] + (EXT if k == 0 else INT)
        labels.append(dict(cx=x0 + w * S / 2, cy=cy, dims=(w, depth)))
    return walls, labels


def check(name, got, want=S, tol=0.01):
    ok = got is not None and abs(got / want - 1) <= tol
    print(("ok  " if ok else "FAIL") + f" {name}: {got if got is None else round(got, 3)} (want {want})")
    return ok


def main():
    good = True
    walls, labels = row([12, 10, 14], 11)
    good &= check("plain row", detect._scale_from_sizes(walls, labels)[0])
    walls, labels = row([12, 10, 14], 11, door_on_ray=True)
    good &= check("doors across the label rays", detect._scale_from_sizes(walls, labels)[0])
    walls, labels = row([12, 10, 14, 9, 11, 13, 10, 12], 11, partitions=False)
    good &= check("partitions missing: depths decide", detect._scale_from_sizes(walls, labels)[0])
    # 9" outer walls with 4.5" partitions: a good share of the wall length is half the main thickness
    walls, _ = row([12, 10, 14], 11)
    pairs = [(w[0], w[1], w[2], w[3]) for w in walls if w[3] - w[2] > w[1] - w[0]]      # vertical: (c0, c1, a0, a1)
    share = detect.half_wall_share(pairs, EXT)
    print(("ok  " if share >= 0.15 else "FAIL") + f" half-thickness share {share:.2f} (>= 0.15)")
    good &= share >= 0.15
    if not good:
        sys.exit(1)


if __name__ == "__main__":
    main()
