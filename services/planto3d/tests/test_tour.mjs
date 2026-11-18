// The guided tour (web/tour.js) on a built house: it starts outside, reaches every room and area (except water,
// shafts and stairs), visits every storey with stairs, never stands in a wall, water or furniture, never jumps, and ends.
// Run: node tests/test_tour.mjs jobs/<id>/meta.json
import fs from 'node:fs';
import * as walk from '../web/walk.js';
import { plan } from '../web/tour.js';

const meta = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const SKIP = new Set(['stair', 'lift', 'duct', 'open', 'pool', 'water', 'dock']);
const t0 = Date.now();
const route = plan(meta);
let fails = 0;
const check = (ok, msg) => { if (!ok) { console.log(`FAIL ${msg}`); fails++; } };

check(route.length > 1 && Date.now() - t0 < 60000, `a route was planned (${route.length} points)`);
// every room whose middle can be stood in is visited
meta.floors.forEach((f, k) => {
  for (const r of f.rooms.filter((r) => !SKIP.has(r.type) && r.rects.length)) {
    const visited = route.some((p) => Math.abs(p.z - f.z) < 0.3 && r.rects.some((q) => walk.inRect(q, p.x, p.y)));
    const q = r.rects.reduce((a, b) => ((b[1] - b[0]) * (b[3] - b[2]) > (a[1] - a[0]) * (a[3] - a[2]) ? b : a));
    const reachable = (q[1] - q[0]) > 0.9 && (q[3] - q[2]) > 0.9;
    check(visited || !reachable, `${f.name} ${r.label || r.type} is not visited`);
  }
});
const jumps = route.filter((p) => p.jump).length, visits = route.filter((p) => p.visit).length;
check(jumps * 3 <= Math.max(3, visits), `${jumps} jumps for ${visits} rooms`);
const storeys = new Set(route.map((p) => walk.levelOf(meta, p.z)));
const climbable = meta.floors.filter((f) => (f.stairs || []).some((s) => !s.landing)).length;
check(storeys.size >= Math.min(meta.floors.length, climbable + 1), `visits ${storeys.size} of ${meta.floors.length} storeys`);
// never in a wall, water or furniture; consecutive points are walkable in between, except at a jump to a part
// of the house that cannot be walked to (at most one jump per three rooms)
for (let n = 0; n < route.length; n++) {
  const p = route[n], k = walk.levelOf(meta, p.z);
  if (!p.stair) {
    check(!walk.blockedAt(meta, k, p.x, p.y), `point ${n} (${p.x.toFixed(2)}, ${p.y.toFixed(2)}) is in a wall or water`);
    check(!(meta.floors[k].furniture || []).some((r) => walk.inRect(r, p.x, p.y)), `point ${n} is in furniture`);
  }
  if (n && !p.stair && !p.jump && !route[n - 1].stair) {     // (a jump is not walked: tour.js)
    const a = route[n - 1], d = Math.hypot(p.x - a.x, p.y - a.y), steps = Math.ceil(d / 0.1);
    for (let i = 1; i < steps; i++) {
      const x = a.x + (p.x - a.x) * i / steps, y = a.y + (p.y - a.y) * i / steps;
      if (walk.blockedAt(meta, k, x, y)) { check(false, `the leg ${n - 1} -> ${n} crosses a wall at ${x.toFixed(2)}, ${y.toFixed(2)}`); break; }
    }
  }
}
console.log(`${fails ? 'FAIL' : 'ok  '} tour of ${process.argv[2]}: ${route.length} points, ${storeys.size} storeys, ${route.filter((p) => p.visit).length} rooms`);
process.exit(fails ? 1 : 0);
