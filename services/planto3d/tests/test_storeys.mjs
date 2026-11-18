// Outdoors on an upper storey: on every balcony, sit-out, terrace or yard of a storey above the ground, the walker
// stands on that storey's floor, and walking across it and on towards every side never takes it to another height
// (it stops at the edge) and never changes the storey the page names.  Run: node tests/test_storeys.mjs jobs/<id>/meta.json
import fs from 'node:fs';
import * as walk from '../web/walk.js';

const meta = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const OUTDOOR = ['balcony', 'garden', 'yard', 'parking'];
let fails = 0, n = 0;
const check = (ok, msg) => { n++; if (!ok) { console.log(`FAIL ${msg}`); fails++; } };

// over a room of this storey, or its walls (not out in the air past the building)
const overRooms = (f, p) => f.rooms.some((r) => r.type !== 'open' && r.rects.some((q) => walk.inRect(q, p.x, p.y, 0.45)));
const onStairs = (k, p) => [k - 1, k].some((j) => (meta.floors[j]?.stairs || []).some((s) => walk.inRect(s.rect, p.x, p.y, 0.25)));

meta.floors.forEach((f, k) => {
  if (!f.floor) return;                 // on the ground: walking off it is fine
  for (const room of f.rooms.filter((r) => OUTDOOR.includes(r.type))) {
    for (const q of room.rects) {
      const cx = (q[0] + q[1]) / 2, cy = (q[2] + q[3]) / 2;
      if (walk.groundNear(meta, cx, cy, f.z) === null || walk.blockedAt(meta, k, cx, cy)) continue;   // (a void)
      check(walk.groundNear(meta, cx, cy, f.z) === f.z, `${f.name} ${room.label}: no floor at the storey's height`);
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const p = { x: cx, y: cy, z: f.z };
        let ok = true;
        for (let i = 0; i < 600 && ok; i++) {          // 18 m: across the room and well past the building
          walk.move(meta, p, dx * 0.03, dy * 0.03);
          if (onStairs(k, p)) break;                   // a stair that starts out here may take it up or down
          ok = Math.abs(p.z - f.z) < 0.01 && walk.levelOf(meta, p.z) === k && overRooms(f, p);
        }
        check(ok, `${f.name} ${room.label}: walking ${dx ? (dx > 0 ? 'east' : 'west') : (dy > 0 ? 'north' : 'south')} `
          + `took the walker to ${p.z.toFixed(2)} m (storey ${walk.levelOf(meta, p.z)}) at ${p.x.toFixed(2)}, ${p.y.toFixed(2)}`);
      }
    }
  }
});
console.log(`${fails ? 'FAIL' : 'ok  '} upper-storey outdoors of ${process.argv[2]}: ${n - fails}/${n} checks pass`);
process.exit(fails ? 1 : 0);
