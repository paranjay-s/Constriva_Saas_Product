"""The Blender queue's lanes (server.Lanes, server.builder) with Blender stubbed: no render.

A tour and a High bake are queued (heavy lane) while a Low build arrives (fast lane): the Low build runs first. A High
build runs its Low step, hands the High bake to the heavy lane and lets other fast work in before it.
"""
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import server  # noqa: E402

order, statuses = [], {}
gate = threading.Event()


def run_blender(jid, quality, d, t0, a=0, b=100):
    if not gate.is_set():
        gate.wait(10)
    order.append((jid, quality))
    return []


def run_tour(jid, tq, secs, res):
    order.append((jid, "tour"))
    return "tour_high.mp4", None


def status(jid, **kw):
    statuses.setdefault(jid, {}).update(kw)


tmp = tempfile.mkdtemp()
server.run_blender, server.run_tour, server.status = run_blender, run_tour, status
server.read_status = lambda jid: statuses.get(jid)
server.estimate = lambda jid, q: 1
server.calibrate = lambda *a: None
server.jdir = lambda jid: os.path.join(tmp, jid)
server.builds = server.Lanes()
for j in ("busy00000000", "tour00000000", "high00000000", "lowa00000000"):
    os.makedirs(os.path.join(tmp, j))
    statuses[j] = {"stage": "done"}

worker = threading.Thread(target=server.builder, daemon=True)
worker.start()
server.builds.put(("busy00000000", "draft"))                  # holds the builder until the gate opens
server.builds.put(("tour00000000", ("tour", "high", None, None)), "heavy")
server.builds.put(("high00000000", "high"))                    # its Low step is fast work
server.builds.put(("lowa00000000", "draft"))
gate.set()
server.builds.q.join()

want = [("busy00000000", "draft"), ("high00000000", "draft"), ("lowa00000000", "draft"),
        ("tour00000000", "tour"), ("high00000000", "high")]
assert order == want, order
assert statuses["high00000000"]["stage"] == "done" and statuses["high00000000"]["quality"] == "high", statuses["high00000000"]
assert statuses["lowa00000000"]["stage"] == "done"
print("ok   lanes: Low work runs before queued tours and High bakes; a High build's Low step is fast work")
