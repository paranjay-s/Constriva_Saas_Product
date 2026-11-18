// The guided tour's route, planned from meta.json (plan metres: x right, y forward, z up): start outside facing the
// front door, go in, visit every room and area once (nearest first), climb the stairs storey by storey, and end on the
// top storey. Walks on a 0.2 m grid round walls, water, shafts and furniture (walk.js rules), shortcut where the way is
// clear. Pure: used by view.js (the "Guided tour" button) and tests/test_tour.mjs.
import * as walk from './walk.js';

const CELL = 0.2, CLEAR = 0.1;          // grid step and how far furniture is kept from the walker's centre, metres
const SKIP = new Set(['stair', 'lift', 'duct', 'open', 'pool', 'water', 'dock']);

function grid(meta, k) {
  // the house's bounds, grown to every room and area of the storey (a court or a helipad far out on the site)
  let [x0, x1, y0, y1] = meta.bounds;
  for (const r of meta.floors[k].rooms) for (const q of r.rects) {
    x0 = Math.min(x0, q[0]); x1 = Math.max(x1, q[1]); y0 = Math.min(y0, q[2]); y1 = Math.max(y1, q[3]);
  }
  const pad = 6;
  const nx = Math.ceil((x1 - x0 + 2 * pad) / CELL), ny = Math.ceil((y1 - y0 + 2 * pad) / CELL);
  const f = meta.floors[k], furn = f.furniture || [];
  const ok = new Uint8Array(nx * ny);
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    const x = x0 - pad + (i + 0.5) * CELL, y = y0 - pad + (j + 0.5) * CELL;
    if (walk.blockedAt(meta, k, x, y)) continue;
    const g = walk.groundNear(meta, x, y, f.z);
    if (g === null || Math.abs(g - f.z) > 0.05) continue;          // stairs are walked flight by flight, not planned
    if (furn.some((r) => x > r[0] - CLEAR && x < r[1] + CLEAR && y > r[2] - CLEAR && y < r[3] + CLEAR)) continue;
    ok[j * nx + i] = 1;
  }
  return { k, nx, ny, ok, ox: x0 - pad, oy: y0 - pad, z: f.z };
}

const cellOf = (G, x, y) => [Math.floor((x - G.ox) / CELL), Math.floor((y - G.oy) / CELL)];
const centre = (G, i, j) => [G.ox + (i + 0.5) * CELL, G.oy + (j + 0.5) * CELL];
const free = (G, i, j) => i >= 0 && j >= 0 && i < G.nx && j < G.ny && G.ok[j * G.nx + i] === 1;

/** the free cell nearest to (x, y), within r metres */
function nearestFree(G, x, y, r = 2.5) {
  const [ci, cj] = cellOf(G, x, y), n = Math.ceil(r / CELL);
  let best = null;
  for (let dj = -n; dj <= n; dj++) for (let di = -n; di <= n; di++) {
    if (!free(G, ci + di, cj + dj)) continue;
    const d = di * di + dj * dj;
    if (!best || d < best[0]) best = [d, ci + di, cj + dj];
  }
  return best && [best[1], best[2]];
}

/** breadth-first distances from a cell (4-neighbour, unit cost): -> Int32Array, -1 where unreachable */
function bfs(G, s) {
  const dist = new Int32Array(G.nx * G.ny).fill(-1), q = [s[1] * G.nx + s[0]];
  dist[q[0]] = 0;
  for (let h = 0; h < q.length; h++) {
    const c = q[h], i = c % G.nx, j = (c - i) / G.nx;
    for (const [a, b] of [[i + 1, j], [i - 1, j], [i, j + 1], [i, j - 1]]) {
      if (free(G, a, b) && dist[b * G.nx + a] < 0) { dist[b * G.nx + a] = dist[c] + 1; q.push(b * G.nx + a); }
    }
  }
  return dist;
}

function pathTo(G, dist, t) {
  const out = [t];
  let [i, j] = t;
  while (dist[j * G.nx + i] > 0) {
    const d = dist[j * G.nx + i];
    [i, j] = [[i + 1, j], [i - 1, j], [i, j + 1], [i, j - 1]].find(([a, b]) => free(G, a, b) && dist[b * G.nx + a] === d - 1);
    out.push([i, j]);
  }
  return out.reverse();
}

/** straight runs where the way is clear (line of sight over free cells) */
function shortcut(G, cells) {
  if (cells.length < 3) return cells;
  const clear = (a, b) => {
    const n = Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) * 2);
    for (let t = 1; t < n; t++) {
      const i = Math.round(a[0] + (b[0] - a[0]) * t / n), j = Math.round(a[1] + (b[1] - a[1]) * t / n);
      if (!free(G, i, j) || !free(G, i + 1, j) || !free(G, i - 1, j) || !free(G, i, j + 1) || !free(G, i, j - 1)) return false;
    }
    return true;
  };
  const out = [cells[0]];
  let a = 0;
  while (a < cells.length - 1) {
    let b = cells.length - 1;
    while (b > a + 1 && !clear(cells[a], cells[b])) b--;
    out.push(cells[b]);
    a = b;
  }
  return out;
}

/** the best place to stand in a room: its free cell nearest the middle of its largest rectangle */
function roomSpot(G, r) {
  const q = r.rects.reduce((a, b) => ((b[1] - b[0]) * (b[3] - b[2]) > (a[1] - a[0]) * (a[3] - a[2]) ? b : a));
  const c = nearestFree(G, (q[0] + q[1]) / 2, (q[2] + q[3]) / 2, Math.max(q[1] - q[0], q[3] - q[2]) / 2);
  return c && { cell: c, area: r.rects.reduce((s, p) => s + (p[1] - p[0]) * (p[3] - p[2]), 0), label: r.label || r.type };
}

/** the front door: a ground-storey door with no room on one side; -> {outside: [x, y], inside: [x, y]}. A door whose
 *  roomless side is beyond the house's bounds wins (the other kind may open on an unlabelled hall or a light well);
 *  of those, the lowest (the plan's entrance side). */
function frontDoor(meta) {
  const f = meta.floors[0];
  const inRoom = (x, y) => f.rooms.some((r) => r.rects.some((q) => walk.inRect(q, x, y)));
  const beyond = ([x, y]) => !walk.inRect(meta.bounds, x, y, -0.1);
  let best = null;
  for (const o of f.openings || []) {
    if (o.type === 'window' || o.built === 'window') continue;
    const r = o.rect, cx = (r[0] + r[1]) / 2, cy = (r[2] + r[3]) / 2, across = r[1] - r[0] < r[3] - r[2];
    const a = across ? [r[0] - 2.5, cy] : [cx, r[2] - 2.5], b = across ? [r[1] + 2.5, cy] : [cx, r[3] + 2.5];
    if (inRoom(...a) === inRoom(...b)) continue;
    const d = inRoom(...a) ? { outside: b, inside: a } : { outside: a, inside: b };
    const rank = [beyond(d.outside) ? 0 : 1, cy];
    if (!best || rank[0] < best.rank[0] || (rank[0] === best.rank[0] && rank[1] < best.rank[1])) best = { ...d, rank };
  }
  return best && { outside: best.outside, inside: best.inside };
}

/** -> [{x, y, z, room, pause}] : the whole route, ending on the top storey reached */
export function plan(meta) {
  const route = [];
  const push = (G, cells, extra = {}) => cells.forEach((c, n) => {
    const [x, y] = centre(G, ...c);
    route.push({ x, y, z: G.z, room: walk.roomAt(meta, G.k, x, y), ...(n === cells.length - 1 ? extra : {}) });
  });
  let at = null, arrived = null;          // grid cell; where the last stair ended (metres)
  for (let k = 0; k < meta.floors.length; k++) {
    const G = grid(meta, k);
    if (k === 0) {
      const door = frontDoor(meta);
      const e = walk.entrance(meta);
      at = (door && nearestFree(G, ...door.outside)) || nearestFree(G, e.x, (meta.bounds[2]) - 3) || nearestFree(G, e.x, e.y);
      if (!at) return route;
      push(G, [at]);
    } else {
      at = nearestFree(G, ...arrived, 1.5);
      if (!at) break;
    }
    const f = meta.floors[k];
    let todo = f.rooms.filter((r) => !SKIP.has(r.type) && r.rects.length).map((r) => roomSpot(G, r)).filter(Boolean);
    while (todo.length) {                       // nearest room next
      const dist = bfs(G, at);
      const reach = todo.filter((t) => dist[t.cell[1] * G.nx + t.cell[0]] >= 0);
      if (!reach.length) {
        // the rest cannot be walked to from here (a wing reached only through a closed court, a door the plan
        // misses): jump to the nearest of them; the player moves the walker there at once
        const [x, y] = centre(G, ...at);
        todo.sort((a, b) => Math.hypot(...centre(G, ...a.cell).map((v, i) => v - [x, y][i])) -
                            Math.hypot(...centre(G, ...b.cell).map((v, i) => v - [x, y][i])));
        const t = todo.shift();
        push(G, [t.cell], { jump: true, pause: t.area >= 9 ? 2 : 0, visit: t.label });
        at = t.cell;
        continue;
      }
      const d = (t) => dist[t.cell[1] * G.nx + t.cell[0]];
      const t = reach.reduce((a, b) => (d(b) < d(a) ? b : a));       // the nearest one that can be walked to
      todo = todo.filter((u) => u !== t);
      push(G, shortcut(G, pathTo(G, dist, t.cell)).slice(1), { pause: t.area >= 9 ? 2 : 0, visit: t.label });
      at = t.cell;
    }
    // up the stairs to the next storey (as tests/test_walk.mjs climbs them)
    const flights = (f.stairs || []).filter((s) => !s.landing);
    if (k + 1 >= meta.floors.length || !flights.length) break;
    const s0 = flights[0];
    const mid = (r, ax) => (ax === 'x' ? (r[2] + r[3]) / 2 : (r[0] + r[1]) / 2);
    const foot = s0.axis === 'x' ? [s0.start - s0.dir * 0.4, mid(s0.rect, 'x')] : [mid(s0.rect, 'y'), s0.start - s0.dir * 0.4];
    const fc = nearestFree(G, ...foot, 1.5);
    if (!fc) break;
    const dist = bfs(G, at);
    if (dist[fc[1] * G.nx + fc[0]] < 0) break;
    push(G, shortcut(G, pathTo(G, dist, fc)).slice(1));
    const p = { x: foot[0], y: foot[1], z: f.z };
    for (const s of flights) {
      const len = s.axis === 'x' ? s.rect[1] - s.rect[0] : s.rect[3] - s.rect[2];
      const end = s.start + s.dir * (len + 0.35);
      const line = [s.axis === 'x' ? p.x : mid(s.rect, 'y'), s.axis === 'x' ? mid(s.rect, 'x') : p.y];
      const top = [s.axis === 'x' ? end : line[0], s.axis === 'x' ? line[1] : end];
      for (const [x, y] of [line, top]) {
        for (let n = 0; n < 400 && Math.hypot(x - p.x, y - p.y) > 0.03; n++) {
          const d = Math.hypot(x - p.x, y - p.y), st = Math.min(0.04, d);
          walk.move(meta, p, (x - p.x) / d * st, (y - p.y) / d * st);
        }
        route.push({ x: p.x, y: p.y, z: p.z, room: walk.roomAt(meta, walk.levelOf(meta, p.z), p.x, p.y), stair: true });
      }
    }
    if (walk.levelOf(meta, p.z) !== k + 1) break;     // the stair did not reach the next storey
    arrived = [p.x, p.y];
  }
  return route;
}
