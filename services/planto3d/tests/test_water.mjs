// Water and shafts: the walker cannot stand in a pool, a water body, a dock's water or a lift / duct shaft, and can
// stand on a dock's deck.  Run: node tests/test_water.mjs jobs/<id>/meta.json
import fs from 'node:fs';
import * as walk from '../web/walk.js';

const meta = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const rooms = JSON.parse(fs.readFileSync(new URL('../web/rooms.json', import.meta.url), 'utf8'));
const kind = (t) => rooms.types[t]?.kind;
let fails = 0, n = 0;
const check = (ok, msg) => { n++; if (!ok) { console.log(`FAIL ${msg}`); fails++; } };

meta.floors.forEach((f, k) => {
  for (const r of f.rooms) {
    if (!['water', 'shaft'].includes(kind(r.type))) continue;
    for (const q of r.rects) {
      const cx = (q[0] + q[1]) / 2, cy = (q[2] + q[3]) / 2;
      check(walk.blockedAt(meta, k, cx, cy), `${f.name} ${r.label}: the walker can stand in the middle of the ${r.type}`);
      if (r.type !== 'dock') continue;
      // the deck runs along the long sides: a point just inside a long edge is walkable
      const long = q[1] - q[0] >= q[3] - q[2];
      const [x, y] = long ? [cx, q[2] + 0.5] : [q[0] + 0.5, cy];
      check(!walk.blockedAt(meta, k, x, y) && walk.groundNear(meta, x, y, f.z) !== null, `${f.name} ${r.label}: the dock deck is not walkable at ${x.toFixed(2)}, ${y.toFixed(2)}`);
    }
  }
});
console.log(`${fails ? 'FAIL' : 'ok  '} water and shafts of ${process.argv[2]}: ${n - fails}/${n} checks pass`);
process.exit(fails ? 1 : 0);
