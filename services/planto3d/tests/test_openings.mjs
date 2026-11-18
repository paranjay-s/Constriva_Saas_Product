// Every opening of a built house is what the plan says it is: plan.json against meta.json (what gen.py built) and
// the walker (walk.js). A door or plain opening is cut to the floor, at least 2 m high, and the walker goes through
// it; a window has a sill and the walker cannot climb through it.  Run: node tests/test_openings.mjs jobs/<id>
// (a plan edited after its build fails here until it is built again)
import fs from 'node:fs';
import path from 'node:path';
import * as walk from '../web/walk.js';

const dir = process.argv[2];
const plan = JSON.parse(fs.readFileSync(path.join(dir, 'plan.json'), 'utf8'));
const meta = JSON.parse(fs.readFileSync(path.join(dir, 'meta.json'), 'utf8'));
const F = 0.3048;
let fails = 0, n = 0;
const check = (ok, msg) => { n++; if (!ok) { console.log(`FAIL ${msg}`); fails++; } };

/** can the walker cross the wall at this opening, from 0.5 m before it to 0.5 m past it? (lanes 5% apart across the
 *  opening, middle first: a side wall may stand in its first inches, and the walker is 0.44 m wide) */
function crosses(k, r, axis) {
  const along = axis === 'x' ? [r[0], r[1]] : [r[2], r[3]];
  const lanes = Array.from({ length: 19 }, (_, i) => 0.05 * (i + 1)).sort((a, b) => Math.abs(a - 0.5) - Math.abs(b - 0.5));
  for (const t of lanes) {
    const a = along[0] + (along[1] - along[0]) * t;
    const p = axis === 'x' ? { x: a, y: r[2] - 0.5, z: meta.floors[k].z } : { x: r[0] - 0.5, y: a, z: meta.floors[k].z };
    const end = axis === 'x' ? r[3] + 0.5 : r[1] + 0.5;
    if (walk.blockedAt(meta, k, p.x, p.y)) continue;
    for (let i = 0; i < 200; i++) {
      const before = axis === 'x' ? p.y : p.x;
      if (before >= end) return true;
      walk.move(meta, p, axis === 'x' ? 0 : 0.03, axis === 'x' ? 0.03 : 0);
      if ((axis === 'x' ? p.y : p.x) === before) break;
    }
  }
  return false;
}

/** is there floor at this storey's height 0.5 m before and 0.5 m past the opening? */
function sides(k, r, axis) {
  const z = meta.floors[k].z, cx = (r[0] + r[1]) / 2, cy = (r[2] + r[3]) / 2;
  const ends = axis === 'x' ? [[cx, r[2] - 0.5], [cx, r[3] + 0.5]] : [[r[0] - 0.5, cy], [r[1] + 0.5, cy]];
  return ends.every(([x, y]) => walk.groundNear(meta, x, y, z) !== null);
}

plan.floors.forEach((f, k) => {
  const built = meta.floors[k]?.openings;
  if (!built) return check(false, `${f.name}: meta.json has no record of the openings that were built`);
  check(built.length === f.openings.length, `${f.name}: ${f.openings.length} openings in the plan, ${built.length} built`);
  f.openings.forEach((o, i) => {
    const b = built[i], tag = `${f.name} opening ${i} (${o.type} at ${o.rect.map((v) => v.toFixed(1)).join(', ')} ft)`;
    if (!b) return;
    const r = o.rect.map((v) => v * F);
    check(b.type === o.type && r.every((v, j) => Math.abs(v - b.rect[j]) < 0.01), `${tag}: built as ${b.type} at ${b.rect}`);
    if (o.type === 'window') {
      check(b.built === 'window' && b.sill > 0.3, `${tag}: built as a ${b.built} with sill ${b.sill} m`);
      check(!crosses(k, r, o.axis), `${tag}: the walker climbs through the window`);
    } else {
      check(b.built === 'doorway' && b.sill === 0 && b.head >= 2.0, `${tag}: built as a ${b.built}, sill ${b.sill} m, head ${b.head} m`);
      // (an opening in an upper storey's outer wall that has no floor beyond it leads nowhere: it stays shut)
      if (sides(k, r, o.axis)) check(crosses(k, r, o.axis), `${tag}: the walker cannot go through`);
    }
  });
});
console.log(`${fails ? 'FAIL' : 'ok  '} openings of ${dir}: ${n - fails}/${n} checks pass`);
process.exit(fails ? 1 : 0);
