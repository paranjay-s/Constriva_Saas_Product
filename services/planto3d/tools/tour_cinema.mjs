// The guided tour's route (web/tour.js) as a TOUR.json for blender/cinema.py: keys in plan feet, the camera at eye
// height looking a few metres ahead along the route, the route's pauses as holds.
//   node tools/tour_cinema.mjs JOB/meta.json TOUR.json [--seconds N] [--speed FT_PER_S]
// --seconds cuts the route to about N seconds of glide (a test clip); jumps (parts the tour cannot walk to) end it.
import fs from 'node:fs';
import path from 'node:path';
import { plan } from '../web/tour.js';

const [metaPath, out, ...rest] = process.argv.slice(2);
const opt = (k, d) => (rest.includes(k) ? Number(rest[rest.indexOf(k) + 1]) : d);
const FT = 0.3048, SPEED = opt('--speed', 1.9), SECONDS = opt('--seconds', Infinity);
const meta = JSON.parse(fs.readFileSync(metaPath, 'utf8'));
const route = plan(meta);
const eye = meta.eye || 1.6;
const keys = [];
let walked = 0;
for (let i = 0; i < route.length; i++) {
  const r = route[i];
  if (i && r.jump) break;                                  // a film cannot jump: end at the first one
  const last = keys.at(-1);
  const d = last ? Math.hypot(r.x - last.m[0], r.y - last.m[1]) : 0;
  if (last && d < 1.2 && !r.pause && i !== route.length - 1) continue;
  walked += d;
  if (walked / FT / SPEED > SECONDS) break;
  // look 2.5 m ahead along the route (or straight on at the end)
  let ahead = route.slice(i + 1).find((q) => Math.hypot(q.x - r.x, q.y - r.y) >= 2.5 && !q.jump);
  if (!ahead && last) ahead = { x: r.x + (r.x - last.m[0]), y: r.y + (r.y - last.m[1]), z: r.z };
  if (!ahead) ahead = { x: r.x, y: r.y + 2.5, z: r.z };
  keys.push({
    m: [r.x, r.y],
    p: [r.x / FT, r.y / FT, (r.z + eye) / FT],
    t: [ahead.x / FT, ahead.y / FT, (ahead.z + eye - 0.15) / FT],
    ...(r.pause ? { hold: r.pause } : {}),
    ...(r.visit ? { room: r.visit } : {}),
  });
}
// cinema.py also reads the plan (rooms, lamps, garden): the job's plan.json beside its meta.json
const tour = { fps: 30, eye: eye / FT, speed: SPEED, plan: path.resolve(path.dirname(metaPath), 'plan.json'), keys: keys.map(({ m, ...k }) => k) };
fs.writeFileSync(out, JSON.stringify(tour));
console.log(`${keys.length} keys, about ${(walked / FT / SPEED).toFixed(1)} s of glide`);
