// Walk test on a generated house: climb every storey's stairs (flight -> landing -> flight) and check we arrive
// on the next floor; and check walls stop the walker.  Run: node tests/test_walk.mjs jobs/<id>/meta.json
import fs from 'node:fs';
import * as walk from '../web/walk.js';

const meta = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
let fails = 0;
const check = (ok, msg) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${msg}`); if (!ok) fails++; };

function goTo(p, tx, ty, maxSteps = 2000) {
  for (let i = 0; i < maxSteps; i++) {
    const dx = tx - p.x, dy = ty - p.y, d = Math.hypot(dx, dy);
    if (d < 0.03) return true;
    const s = Math.min(0.04, d);
    const bx = p.x, by = p.y;
    walk.move(meta, p, dx / d * s, dy / d * s);
    if (p.x === bx && p.y === by) return false;   // stuck
  }
  return false;
}

meta.floors.forEach((f, k) => {
  const flights = (f.stairs || []).filter((s) => !s.landing);
  if (!flights.length) return;
  if (meta.floors.length === 1) {      // a single storey's stairs lead nowhere drawn: the walker must not get onto them
    const s0 = flights[0], mid = s0.axis === 'x' ? (s0.rect[2] + s0.rect[3]) / 2 : (s0.rect[0] + s0.rect[1]) / 2;
    const p = s0.axis === 'x' ? { x: s0.start - s0.dir * 0.6, y: mid, z: f.z } : { x: mid, y: s0.start - s0.dir * 0.6, z: f.z };
    const end = s0.start + s0.dir * 1.5;
    goTo(p, s0.axis === 'x' ? end : p.x, s0.axis === 'x' ? p.y : end);
    check(Math.abs(p.z - f.z) < 0.01 && !walk.inRect(s0.rect, p.x, p.y), `${f.name}: stairs to the roof are closed (stopped at ${p.x.toFixed(2)}, ${p.y.toFixed(2)})`);
    return;
  }
  const target = k + 1 < meta.floors.length ? meta.floors[k + 1].z : meta.roof_z;
  const s0 = flights[0];
  const mid = (r, ax) => (ax === 'x' ? (r[2] + r[3]) / 2 : (r[0] + r[1]) / 2);
  // stand on the floor just before the first step
  const p = s0.axis === 'x' ? { x: s0.start - s0.dir * 0.3, y: mid(s0.rect, 'x'), z: f.z } : { x: mid(s0.rect, 'y'), y: s0.start - s0.dir * 0.3, z: f.z };
  let ok = true;
  for (const s of flights) {
    const len = s.axis === 'x' ? s.rect[1] - s.rect[0] : s.rect[3] - s.rect[2];
    const end = s.start + s.dir * (len + 0.35);
    // line up with this flight (across the landing), then climb it
    ok = ok && goTo(p, s.axis === 'x' ? p.x : mid(s.rect, 'y'), s.axis === 'x' ? mid(s.rect, 'x') : p.y);
    ok = ok && goTo(p, s.axis === 'x' ? end : p.x, s.axis === 'x' ? p.y : end);
  }
  check(ok, `${f.name}: walked up all ${flights.length} flight(s) without getting stuck (at ${p.x.toFixed(2)}, ${p.y.toFixed(2)})`);
  check(Math.abs(p.z - target) < 0.05, `${f.name}: arrived at height ${p.z.toFixed(2)} m (next level ${target.toFixed(2)} m)`);
});

// walls block: walking straight at the first collider of the ground floor must stop before it
const w = meta.floors[0].colliders.find((r) => r[1] - r[0] > 2);
if (w) {
  const y = w[2] - 1.0, x = (w[0] + w[1]) / 2;
  const p = { x, y, z: meta.floors[0].z };
  if (walk.groundNear(meta, x, y, p.z) !== null && !walk.blockedAt(meta, 0, x, y)) {
    goTo(p, x, w[3] + 1.0);
    check(p.y < w[2], `wall at y=${w[2].toFixed(2)} stopped the walker at y=${p.y.toFixed(2)}`);
  }
}
process.exit(fails ? 1 : 0);
