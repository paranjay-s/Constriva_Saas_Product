// Walking rules shared by the viewer and its test: plan metres (x right, y forward, z up).
export const RADIUS = 0.22, STEP = 0.45;
// a single-storey plan's stairs lead to a floor that is not drawn: keep them closed. With 2+ storeys the
// top storey's stairs go up to the roof terrace and stay walkable.
const closed = (meta) => (meta.floors.length === 1 ? 0 : -1);
export const inRect = (r, x, y, m = 0) => x >= r[0] - m && x <= r[1] + m && y >= r[2] - m && y <= r[3] + m;

/** where a visit starts: the middle of the bottom-most room of the lowest storey (the entrance side of the plan).
 *  Voids and stairs do not count; of rooms equally low, the bigger one wins. Yaw 0 then looks up the plan, into the house. */
export function entrance(meta) {
  const area = (q) => (q[1] - q[0]) * (q[3] - q[2]);
  const rooms = meta.floors[0].rooms.filter((r) => !['open', 'stair', 'duct'].includes(r.type) && r.rects.length)
    .map((r) => ({ low: Math.min(...r.rects.map((q) => q[2])), big: r.rects.reduce((a, b) => (area(b) > area(a) ? b : a)) }));
  if (!rooms.length) { const b = meta.bounds; return { x: (b[0] + b[1]) / 2, y: (b[2] + b[3]) / 2 }; }
  const low = Math.min(...rooms.map((r) => r.low));
  const q = rooms.filter((r) => r.low < low + 0.3).sort((a, b) => area(b.big) - area(a.big))[0].big;
  return { x: (q[0] + q[1]) / 2, y: (q[2] + q[3]) / 2 };
}

/** storey k has a floor at (x, y): a storey on the ground everywhere (it stands on the site), one above the ground
 *  only on its slab (`floor`, also written for a lone upper storey built on a block). A house built before the slab
 *  outline was written (no `floor`) keeps the old rule: everywhere. */
export function onFloor(meta, k, x, y) {
  const f = meta.floors[k];
  return !f.floor || f.floor.some((r) => inRect(r, x, y, 0.01));
}

/** what the page names as where you are: the room of storey lv under (x, y), or '' */
export function roomAt(meta, lv, x, y) {
  for (const r of meta.floors[lv]?.rooms || []) for (const q of r.rects) if (inRect(q, x, y)) return r.label;
  return '';
}

export function levelOf(meta, z) {
  let lv = 0;
  meta.floors.forEach((f, i) => { if (z >= f.z - 0.3) lv = i; });
  return lv;
}

export function blockedAt(meta, lv, x, y) {
  const f = meta.floors[lv];
  if (!f) return false;
  for (const r of f.colliders) {
    const cx = Math.max(r[0], Math.min(x, r[1])), cy = Math.max(r[2], Math.min(y, r[3]));
    if ((x - cx) ** 2 + (y - cy) ** 2 < RADIUS * RADIUS) return true;
  }
  if (lv === closed(meta))
    for (const s of f.stairs || []) if (inRect(s.rect, x, y)) return true;   // (not where we come up)
  return false;
}

/** every walkable height under (x, y): storey floors, the roof, stair flights (a ramp) and landings */
// The floor above a stair is cut only where the steps below come within head height of it, and over landings
// (gen.py builds the same hole): over the first steps of a flight there is floor.
export const HEADROOM = 2.1;

function stepHeight(s, x, y) {
  if (s.landing) return s.z0;
  const a = s.axis === 'x' ? x : y;
  const len = s.axis === 'x' ? s.rect[1] - s.rect[0] : s.rect[3] - s.rect[2];
  const t = Math.min(1, Math.max(0, (a - s.start) * s.dir / len));
  return s.z0 + (s.z1 - s.z0) * t;
}

export function heights(meta, x, y) {
  const levels = [...meta.floors.map((f) => f.z), meta.roof_z];
  // (an upper storey's terrace ends at its edge: past it there is no floor at that height, so the walker stops)
  const planes = levels.map((z, k) => (k < meta.floors.length && !onFloor(meta, k, x, y) ? null : z));
  const out = [];
  const shut = closed(meta);
  meta.floors.forEach((f, k) => {
    if (k === shut) return;
    for (const s of f.stairs || []) {
      if (!inRect(s.rect, x, y, 0.05)) continue;
      planes[k] = null;                      // steps cover this floor
      if (stepHeight(s, x, y) > levels[k + 1] - HEADROOM) planes[k + 1] = null;   // the stairwell hole above
    }
  });
  // a raised area one can walk on (gen.py "platforms") replaces the floor under it
  meta.floors.forEach((f, k) => {
    for (const p of f.platforms || []) if (inRect(p.rect, x, y)) { planes[k] = null; out.push(p.z); }
  });
  out.push(...planes.filter((z) => z !== null));
  for (const f of meta.floors.filter((_, k) => k !== shut)) for (const s of f.stairs || []) {
    if (inRect(s.rect, x, y, 0.05)) out.push(stepHeight(s, x, y));
  }
  return out;
}

/** the height closest to z that is within one step, or null (a drop / wall) */
export function groundNear(meta, x, y, z) {
  let best = null;
  for (const h of heights(meta, x, y)) if (Math.abs(h - z) <= STEP && (best === null || Math.abs(h - z) < Math.abs(best - z))) best = h;
  return best;
}

/** move the player p {x, y, z} by (dx, dy), sliding along walls; returns p */
export function move(meta, p, dx, dy) {
  for (const [ddx, ddy] of [[dx, 0], [0, dy]]) {        // one axis at a time: slide along walls
    if (!ddx && !ddy) continue;
    const nx = p.x + ddx, ny = p.y + ddy;
    const g = groundNear(meta, nx, ny, p.z);
    if (g === null) continue;
    if (blockedAt(meta, levelOf(meta, Math.max(g, p.z) - 0.05), nx, ny)) continue;
    p.x = nx; p.y = ny; p.z = g;
  }
  return p;
}
