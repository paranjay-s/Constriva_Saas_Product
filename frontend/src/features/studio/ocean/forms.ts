/**
 * Architectural forms for the ASCII background (they replace the template's jellyfish).
 *
 * Each form draws itself into the offscreen light field with a Pen. The Pen colours every
 * stroke in the field's channels (R = hue A, B = hue B, G = white core) and supports
 * "drafting": while the AI works, only the first part of a form's strokes is drawn, so the
 * form appears line by line like a pen plotter.
 *
 * Blueprint set (floor plan studio): isometric house, tower crane, compass, floor plan,
 * arcade. Brass set (Material Finder): brick panel, herringbone parquet, marble slab,
 * wood planks, swatch fan.
 */

export type Theme = 'blueprint' | 'brass';

export interface Pen {
  g: CanvasRenderingContext2D;
  /** Stroke colour: k = brightness, w = white core. */
  col: (k: number, w?: number) => string;
  /** Count a primitive; false when drafting has not reached it yet. */
  step: () => boolean;
}

export interface FormState {
  t: number; // seconds, scaled by tempo
  k: number; // overall brightness
  facing: number; // compass needle angle (radians, 0 = north)
  seed: number;
}

export interface FormDef {
  /** Draw around (0, 0) at size s (px, roughly the form's radius). */
  draw: (pen: Pen, s: number, st: FormState) => void;
}

type Pt = [number, number];

/** Stroke widths are given for a ~85 px form; strokes are drawn this much thicker. */
const LW = 2.1;

function line(pen: Pen, pts: Pt[], width: number, k: number, w = 0) {
  if (!pen.step()) return;
  const { g } = pen;
  g.lineWidth = width * LW;
  g.strokeStyle = pen.col(k, w);
  g.beginPath();
  g.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) g.lineTo(pts[i][0], pts[i][1]);
  g.stroke();
}

function poly(pen: Pen, pts: Pt[], width: number, k: number, fillK = 0, w = 0) {
  if (!pen.step()) return;
  const { g } = pen;
  g.beginPath();
  g.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) g.lineTo(pts[i][0], pts[i][1]);
  g.closePath();
  if (fillK > 0) {
    g.fillStyle = pen.col(fillK, 0);
    g.fill();
  }
  g.lineWidth = width * LW;
  g.strokeStyle = pen.col(k, w);
  g.stroke();
}

function arc(pen: Pen, cx: number, cy: number, r: number, a0: number, a1: number, width: number, k: number, w = 0) {
  if (!pen.step()) return;
  const { g } = pen;
  g.lineWidth = width * LW;
  g.strokeStyle = pen.col(k, w);
  g.beginPath();
  g.arc(cx, cy, r, a0, a1);
  g.stroke();
}

/** Small deterministic random numbers, so a form looks the same every frame. */
function rng(seed: number) {
  let s = Math.floor(seed * 1e6) || 1;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

// ============================================================== blueprint set

/** Isometric house with a gable roof and a side wing, turning slowly. */
const house: FormDef = {
  draw(pen, s, st) {
    const u = s / 3.4;
    const yaw = Math.sin(st.t * 0.12 + st.seed * 6) * 0.22;
    const cy = Math.cos(yaw), sy = Math.sin(yaw);
    const P = (x: number, y: number, z: number): Pt => {
      const dx = x - 3.75, dy = y - 1.75;
      const rx = dx * cy - dy * sy, ry = dx * sy + dy * cy;
      return [(rx - ry) * u * 0.866, (rx + ry) * u * 0.5 - z * u + u * 0.9];
    };
    const W = 5, D = 3.5, H = 2.2, R = 3.4;
    const k = st.k;
    // soft faces first, then edges
    poly(pen, [P(0, D, 0), P(W, D, 0), P(W, D, H), P(0, D, H)], 1, 0, 0.1 * k);
    poly(pen, [P(W, 0, 0), P(W, D, 0), P(W, D, H), P(W, 0, H)], 1, 0, 0.16 * k);
    poly(pen, [P(0, D, H), P(W, D, H), P(W, D / 2, R), P(0, D / 2, R)], 1, 0, 0.22 * k);
    poly(pen, [P(W, D, 0), P(7.5, D, 0), P(7.5, D, 1.6), P(W, D, 1.6)], 1, 0, 0.1 * k);
    const E = (a: [number, number, number], b: [number, number, number], wd: number, kk: number, ww = 0) =>
      line(pen, [P(...a), P(...b)], wd, kk, ww);
    // slab
    E([-0.6, -0.6, 0], [8.2, -0.6, 0], 2, 0.3 * k);
    E([8.2, -0.6, 0], [8.2, 4.4, 0], 2, 0.3 * k);
    E([8.2, 4.4, 0], [-0.6, 4.4, 0], 2, 0.3 * k);
    E([-0.6, 4.4, 0], [-0.6, -0.6, 0], 2, 0.3 * k);
    // box
    const box: [number, number, number][][] = [
      [[0, 0, 0], [W, 0, 0]], [[W, 0, 0], [W, D, 0]], [[W, D, 0], [0, D, 0]], [[0, D, 0], [0, 0, 0]],
      [[0, 0, H], [W, 0, H]], [[W, 0, H], [W, D, H]], [[W, D, H], [0, D, H]], [[0, D, H], [0, 0, H]],
      [[0, 0, 0], [0, 0, H]], [[W, 0, 0], [W, 0, H]], [[W, D, 0], [W, D, H]], [[0, D, 0], [0, D, H]],
    ];
    for (const [a, b] of box) E(a as never, b as never, 5, 0.62 * k, 0.12 * k);
    // roof
    E([0, D / 2, R], [W, D / 2, R], 6, 0.7 * k, 0.25 * k);
    for (const x of [0, W]) {
      E([x, 0, H], [x, D / 2, R], 5, 0.6 * k, 0.1 * k);
      E([x, D, H], [x, D / 2, R], 5, 0.6 * k, 0.1 * k);
    }
    // wing
    const wing: [number, number, number][][] = [
      [[W, 1, 0], [7.5, 1, 0]], [[7.5, 1, 0], [7.5, D, 0]], [[7.5, D, 0], [W, D, 0]],
      [[W, 1, 1.6], [7.5, 1, 1.6]], [[7.5, 1, 1.6], [7.5, D, 1.6]], [[7.5, D, 1.6], [W, D, 1.6]],
      [[7.5, 1, 0], [7.5, 1, 1.6]], [[7.5, D, 0], [7.5, D, 1.6]],
    ];
    for (const [a, b] of wing) E(a as never, b as never, 4, 0.5 * k);
    // windows and door on the front face
    for (const x0 of [0.6, 2.0, 3.4]) {
      const z0 = 0.9, z1 = 1.8;
      poly(pen, [P(x0, D, z0), P(x0 + 0.9, D, z0), P(x0 + 0.9, D, z1), P(x0, D, z1)], 3, 0.45 * k, 0.12 * k, 0.2 * k);
    }
    poly(pen, [P(5.6, D, 0), P(6.4, D, 0), P(6.4, D, 1.3), P(5.6, D, 1.3)], 3, 0.45 * k, 0.08 * k);
  },
};

/** Tower crane: the trolley runs along the jib and the beam on the hook sways. */
const crane: FormDef = {
  draw(pen, s, st) {
    const u = s / 7;
    const k = st.k;
    const mx = -1.6 * u, mw = 0.9 * u, top = -3.2 * u, mh = 9 * u;
    line(pen, [[mx, top], [mx, top + mh]], 5, 0.6 * k, 0.1 * k);
    line(pen, [[mx + mw, top], [mx + mw, top + mh]], 5, 0.6 * k, 0.1 * k);
    for (let y = top, i = 0; y < top + mh - 1; y += mw, i++) {
      line(pen, i % 2 ? [[mx + mw, y], [mx, y + mw]] : [[mx, y], [mx + mw, y + mw]], 2, 0.35 * k);
    }
    // jib and counter-jib
    line(pen, [[mx - 4 * u, top], [mx + 15 * u, top]], 5, 0.65 * k, 0.15 * k);
    line(pen, [[mx - 4 * u, top + 0.6 * u], [mx + 15 * u, top + 0.35 * u]], 3, 0.4 * k);
    for (let i = 0; i < 38; i++) {
      const x = mx - 4 * u + i * 0.5 * u;
      line(pen, [[x, top], [x + 0.5 * u, top + 0.5 * u]], 1.5, 0.28 * k);
    }
    const ax = mx + mw / 2, ay = top - 2.4 * u;
    line(pen, [[mx, top], [ax, ay], [mx + mw, top]], 3, 0.55 * k);
    line(pen, [[ax, ay], [mx + 11 * u, top]], 1.5, 0.35 * k);
    line(pen, [[ax, ay], [mx - 3.6 * u, top]], 1.5, 0.35 * k);
    poly(pen, [[mx - 3.8 * u, top + 0.6 * u], [mx - 2.2 * u, top + 0.6 * u], [mx - 2.2 * u, top + 1.8 * u], [mx - 3.8 * u, top + 1.8 * u]], 3, 0.5 * k, 0.25 * k);
    poly(pen, [[mx + mw, top + 0.4 * u], [mx + mw + 1.1 * u, top + 0.4 * u], [mx + mw + 1.1 * u, top + 1.4 * u], [mx + mw, top + 1.4 * u]], 3, 0.5 * k, 0.15 * k);
    // trolley, cable, hook and a swinging beam
    const tx = mx + (6 + 6 * (0.5 + 0.5 * Math.sin(st.t * 0.22 + st.seed * 5))) * u;
    const sway = Math.sin(st.t * 0.9 + st.seed) * 0.08;
    const hx = tx + Math.sin(sway) * 5.5 * u, hy = top + Math.cos(sway) * 5.5 * u;
    line(pen, [[tx - 0.4 * u, top + 0.2 * u], [tx + 0.4 * u, top + 0.2 * u]], 5, 0.6 * k, 0.2 * k);
    line(pen, [[tx, top + 0.3 * u], [hx, hy]], 1.5, 0.45 * k, 0.1 * k);
    const bw = 2.6 * u, by = hy + 0.9 * u;
    line(pen, [[hx, hy], [hx - bw * 0.8, by]], 1.5, 0.35 * k);
    line(pen, [[hx, hy], [hx + bw * 0.8, by]], 1.5, 0.35 * k);
    line(pen, [[hx - bw, by], [hx + bw, by]], 7, 0.7 * k, 0.3 * k);
  },
};

/** Compass rose; the needle points to the plan's facing side. */
const compass: FormDef = {
  draw(pen, s, st) {
    const k = st.k;
    const r = s;
    arc(pen, 0, 0, r, 0, Math.PI * 2, 3, 0.5 * k, 0.1 * k);
    arc(pen, 0, 0, r * 0.78, 0, Math.PI * 2, 1.5, 0.3 * k);
    for (let i = 0; i < 72; i++) {
      const a = (i * 5 * Math.PI) / 180;
      const major = i % 6 === 0;
      const r0 = r * (major ? 0.74 : 0.86);
      line(pen, [[Math.cos(a) * r0, Math.sin(a) * r0], [Math.cos(a) * r, Math.sin(a) * r]], major ? 2.5 : 1.2, (major ? 0.55 : 0.3) * k);
    }
    const star = (rot: number, long: number, short: number, kk: number) => {
      const pts: Pt[] = [];
      for (let i = 0; i < 8; i++) {
        const a = rot + (i * Math.PI) / 4;
        const rr = i % 2 === 0 ? long : short;
        pts.push([Math.cos(a) * rr, Math.sin(a) * rr]);
      }
      poly(pen, pts, 2.5, kk, kk * 0.25);
    };
    star(-Math.PI / 2, r * 0.7, r * 0.16, 0.6 * k);
    star(-Math.PI / 2 + Math.PI / 8, r * 0.44, r * 0.12, 0.35 * k);
    // needle
    const a = st.facing + Math.sin(st.t * 0.7 + st.seed) * 0.04;
    const ux = Math.sin(a), uy = -Math.cos(a), nx = -uy, ny = ux;
    poly(pen, [[ux * r * 0.74, uy * r * 0.74], [nx * r * 0.09, ny * r * 0.09], [-ux * r * 0.12, -uy * r * 0.12], [-nx * r * 0.09, -ny * r * 0.09]], 3, 0.9 * k, 0.55 * k, 0.6 * k);
    arc(pen, 0, 0, r * 0.06, 0, Math.PI * 2, 4, 0.8 * k, 0.5 * k);
  },
};

/** Floor plan in plan view: walls, swinging doors, a stair and dimension lines. */
const floorPlan: FormDef = {
  draw(pen, s, st) {
    const k = st.k;
    const w = s * 2.1, h = s * 1.25, x = -w / 2, y = -h / 2;
    const L = (pts: Pt[], wd: number, kk: number, ww = 0) => line(pen, pts, wd, kk * k, ww * k);
    poly(pen, [[x, y], [x + w, y], [x + w, y + h], [x, y + h]], 8, 0.7 * k, 0.05 * k, 0.15 * k);
    L([[x + w * 0.42, y], [x + w * 0.42, y + h * 0.55]], 5, 0.6);
    L([[x, y + h * 0.55], [x + w * 0.62, y + h * 0.55]], 5, 0.6);
    L([[x + w * 0.62, y + h * 0.55], [x + w * 0.62, y + h]], 5, 0.6);
    L([[x + w * 0.78, y], [x + w * 0.78, y + h * 0.4]], 5, 0.6);
    L([[x + w * 0.62, y + h * 0.4], [x + w, y + h * 0.4]], 5, 0.6);
    const door = (cx: number, cy: number, r: number, a0: number, i: number) => {
      const open = (0.55 + 0.45 * Math.sin(st.t * 0.5 + i * 1.7 + st.seed * 3)) * (Math.PI / 2);
      arc(pen, cx, cy, r, a0, a0 + Math.PI / 2, 1.5, 0.3 * k);
      L([[cx, cy], [cx + Math.cos(a0 + open) * r, cy + Math.sin(a0 + open) * r]], 3, 0.65, 0.2);
    };
    door(x + w * 0.42, y + h * 0.3, h * 0.16, Math.PI / 2, 0);
    door(x + w * 0.3, y + h * 0.55, h * 0.16, -Math.PI / 2, 1);
    door(x + w * 0.62, y + h * 0.75, h * 0.16, Math.PI, 2);
    door(x + w * 0.88, y + h * 0.4, h * 0.14, -Math.PI / 2, 3);
    for (let i = 0; i < 8; i++) {
      const yy = y + h * 0.48 + i * h * 0.06;
      L([[x + w * 0.66, yy], [x + w * 0.76, yy]], 1.5, 0.35);
    }
    for (const fx of [0.12, 0.55, 0.86]) {
      L([[x + w * fx, y - 5], [x + w * (fx + 0.09), y - 5]], 1.5, 0.4);
      L([[x + w * fx, y + 5], [x + w * (fx + 0.09), y + 5]], 1.5, 0.4);
    }
    const dy = y + h + 24;
    L([[x, dy], [x + w, dy]], 1.5, 0.3);
    for (const tx of [x, x + w * 0.42, x + w * 0.62, x + w]) L([[tx - 6, dy + 6], [tx + 6, dy - 6]], 2.5, 0.45);
    const dx = x - 24;
    L([[dx, y], [dx, y + h]], 1.5, 0.3);
    for (const ty of [y, y + h * 0.55, y + h]) L([[dx - 6, ty + 6], [dx + 6, ty - 6]], 2.5, 0.45);
  },
};

/** Arches on columns; light runs along them. */
const arcade: FormDef = {
  draw(pen, s, st) {
    const k = st.k;
    const n = 4, bay = s * 0.62, h = s * 1.2;
    const x0 = (-n * bay) / 2, y0 = -h / 2;
    line(pen, [[x0 - 18, y0 - 22], [x0 + n * bay + 18, y0 - 22]], 3, 0.4 * k);
    line(pen, [[x0 - 10, y0 - 8], [x0 + n * bay + 10, y0 - 8]], 5, 0.55 * k, 0.1 * k);
    for (let i = 0; i < n; i++) {
      const glow = 0.55 + 0.45 * Math.sin(st.t * 1.1 - i * 0.9 + st.seed * 4);
      const bx = x0 + i * bay, cw = bay * 0.16;
      line(pen, [[bx, y0 + bay * 0.5], [bx, y0 + h]], 5, 0.6 * k);
      line(pen, [[bx + cw, y0 + bay * 0.5], [bx + cw, y0 + h]], 3, 0.4 * k);
      arc(pen, bx + cw / 2 + bay / 2, y0 + bay * 0.5, (bay - cw) / 2, Math.PI, Math.PI * 2, 5, 0.7 * k * glow, 0.3 * k * glow);
      arc(pen, bx + cw / 2 + bay / 2, y0 + bay * 0.5, (bay - cw) / 2 - 8, Math.PI, Math.PI * 2, 1.5, 0.3 * k);
    }
    line(pen, [[x0 + n * bay, y0 + bay * 0.5], [x0 + n * bay, y0 + h]], 5, 0.6 * k);
    for (let i = 0; i < 3; i++) {
      const yy = y0 + h + 6 + i * 9;
      line(pen, [[x0 - 12 - i * 10, yy], [x0 + n * bay + 12 + i * 10, yy]], 2.5, 0.35 * k);
    }
  },
};

// ================================================================== brass set

function rotator(angle: number) {
  const c = Math.cos(angle), s = Math.sin(angle);
  return (x: number, y: number): Pt => [x * c - y * s, x * s + y * c];
}

/** Brick bond panel; courses light up one row at a time. */
const brick: FormDef = {
  draw(pen, s, st) {
    const k = st.k;
    const R = rotator(-0.2 + Math.sin(st.t * 0.1 + st.seed) * 0.03);
    const w = s * 2.1, h = s * 1.4, bw = s * 0.36, bh = s * 0.15;
    let row = 0;
    for (let y = -h / 2; y < h / 2 - 1; y += bh, row++) {
      const glow = 0.55 + 0.45 * Math.sin(st.t * 1.2 - row * 0.7 + st.seed * 5);
      const off = row % 2 ? bw / 2 : 0;
      for (let x = -w / 2 - off; x < w / 2; x += bw) {
        const a = Math.max(-w / 2, x), b = Math.min(w / 2, x + bw - 5);
        if (b - a < 6) continue;
        poly(pen, [R(a, y), R(b, y), R(b, y + bh - 5), R(a, y + bh - 5)], 3, 0.6 * k * glow, 0.16 * k * glow, 0.1 * k);
      }
    }
  },
};

/** Herringbone parquet; blocks brighten in a slow wave. */
const herringbone: FormDef = {
  draw(pen, s, st) {
    const k = st.k;
    const R = rotator(0.18);
    const w = s * 1.8, h = s * 1.6, Lb = s * 0.42, T = s * 0.12;
    poly(pen, [R(-w / 2, -h / 2), R(w / 2, -h / 2), R(w / 2, h / 2), R(-w / 2, h / 2)], 5, 0.65 * k, 0, 0.15 * k);
    for (let i = -1; i < w / T + 1; i++) {
      for (let j = -1; j < (h / Lb) * 2 + 1; j++) {
        const bx = -w / 2 + i * T, by = -h / 2 + (j * Lb) / 2 + (i % 2) * (Lb / 4);
        const pts: Pt[] = (i + j) % 2
          ? [[bx, by], [bx + Lb * 0.7, by + Lb * 0.7], [bx + Lb * 0.7 - T * 0.7, by + Lb * 0.7 + T * 0.7], [bx - T * 0.7, by + T * 0.7]]
          : [[bx, by], [bx - Lb * 0.7 + T, by + Lb * 0.7], [bx - Lb * 0.7 + T + T * 0.7, by + Lb * 0.7 + T * 0.7], [bx + T * 0.7, by + T * 0.7]];
        if (!pts.every(([px, py]) => Math.abs(px) <= w / 2 && Math.abs(py) <= h / 2)) continue;
        const glow = 0.5 + 0.5 * Math.sin(st.t * 0.9 - (i + j) * 0.35 + st.seed * 2);
        poly(pen, pts.map(([px, py]) => R(px, py)), 1.8, 0.45 * k * glow, 0.1 * k * glow);
      }
    }
  },
};

/** Marble slab; light flows along the veins. */
const marble: FormDef = {
  draw(pen, s, st) {
    const k = st.k;
    const R = rotator(0.12);
    const w = s * 2.0, h = s * 1.45;
    poly(pen, [R(-w / 2, -h / 2), R(w / 2, -h / 2), R(w / 2, h / 2), R(-w / 2, h / 2)], 5, 0.65 * k, 0.1 * k, 0.15 * k);
    const rand = rng(st.seed + 0.37);
    const { g } = pen;
    for (let v = 0; v < 7; v++) {
      let px = -w / 2 + rand() * w * 0.3, py = -h / 2 + rand() * h, ang = -0.6 + rand() * 0.9;
      const pts: Pt[] = [];
      for (let i = 0; i < 60; i++) {
        pts.push(R(px, py));
        ang += (rand() - 0.5) * 0.7;
        px += s * 0.06 * Math.cos(ang);
        py += s * 0.06 * Math.sin(ang);
        if (Math.abs(px) > w / 2 || Math.abs(py) > h / 2) break;
      }
      if (pts.length < 3) continue;
      const main = v < 2;
      line(pen, pts, main ? 4 : 1.8, (main ? 0.55 : 0.3) * k, main ? 0.15 * k : 0);
      if (main && pen.step()) {
        // a bright pulse running along the vein
        g.save();
        g.setLineDash([s * 0.25, s * 1.4]);
        g.lineDashOffset = -st.t * s * 0.35;
        g.lineWidth = 5;
        g.strokeStyle = pen.col(0.6 * k, 0.5 * k);
        g.beginPath();
        g.moveTo(pts[0][0], pts[0][1]);
        for (const [x, y] of pts.slice(1)) g.lineTo(x, y);
        g.stroke();
        g.restore();
      }
    }
  },
};

/** Wood planks; the grain ripples. */
const wood: FormDef = {
  draw(pen, s, st) {
    const k = st.k;
    const R = rotator(-0.14);
    const w = s * 2.1, h = s * 1.45, n = 5, ph = h / n;
    for (let p = 0; p < n; p++) {
      const y0 = -h / 2 + p * ph;
      poly(pen, [R(-w / 2, y0), R(w / 2, y0), R(w / 2, y0 + ph - 4), R(-w / 2, y0 + ph - 4)], 3.5, 0.55 * k, (0.06 + 0.04 * (p % 3)) * k);
      for (let gr = 0; gr < 3; gr++) {
        const gy = y0 + ph * (0.25 + gr * 0.25);
        const pts: Pt[] = [];
        for (let i = 0; i <= 40; i++) {
          const x = -w / 2 + (w * i) / 40;
          pts.push(R(x, gy + Math.sin(i * 0.45 + p + gr + st.t * 0.8) * ph * 0.08));
        }
        line(pen, pts, 1.6, 0.3 * k);
      }
    }
  },
};

/** Swatch fan; the samples open and close like a material book. */
const swatchFan: FormDef = {
  draw(pen, s, st) {
    const k = st.k;
    const spread = 0.2 + 0.07 * Math.sin(st.t * 0.35 + st.seed * 4);
    const n = 9, len = s * 1.9, wd = s * 0.3;
    const py = s * 0.9;
    for (let i = 0; i < n; i++) {
      const a = -Math.PI / 2 + (i - (n - 1) / 2) * spread;
      const ca = Math.cos(a), sa = Math.sin(a), nx = -sa, ny = ca;
      const P = (t: number, q: number): Pt => [ca * t + nx * q, py + sa * t + ny * q];
      poly(pen, [P(s * 0.15, -wd / 2), P(len, -wd / 2), P(len, wd / 2), P(s * 0.15, wd / 2)], 3, 0.6 * k, (0.08 + i * 0.025) * k, 0.1 * k);
      line(pen, [P(len - s * 0.18, -wd / 2), P(len - s * 0.18, wd / 2)], 1.5, 0.35 * k);
    }
    arc(pen, 0, py, s * 0.07, 0, Math.PI * 2, 5, 0.75 * k, 0.4 * k);
  },
};

// ================================================================== layouts

export interface Placement {
  form: FormDef;
  /** Position as a share of the background width / height. */
  x: number;
  y: number;
  /** Size relative to the base size, and depth (0..1, brighter when near). */
  scale: number;
  z: number;
  /** Shown from this many forms on (phones show fewer). */
  minCount: number;
  /** Hue mix between colour A (0) and colour B (1). */
  mix: number;
}

export const LAYOUTS: Record<Theme, Placement[]> = {
  blueprint: [
    { form: house, x: 0.17, y: 0.27, scale: 1.05, z: 0.95, minCount: 1, mix: 0.12 },
    { form: crane, x: 0.83, y: 0.2, scale: 1, z: 0.9, minCount: 1, mix: 0.85 },
    { form: floorPlan, x: 0.84, y: 0.8, scale: 0.95, z: 0.85, minCount: 1, mix: 0.3 },
    { form: compass, x: 0.12, y: 0.8, scale: 0.7, z: 0.75, minCount: 4, mix: 0.6 },
    { form: arcade, x: 0.5, y: 0.11, scale: 0.62, z: 0.45, minCount: 5, mix: 0.45 },
  ],
  brass: [
    { form: brick, x: 0.16, y: 0.25, scale: 1, z: 0.95, minCount: 1, mix: 0.15 },
    { form: herringbone, x: 0.85, y: 0.24, scale: 1, z: 0.9, minCount: 1, mix: 0.75 },
    { form: wood, x: 0.85, y: 0.8, scale: 0.95, z: 0.85, minCount: 1, mix: 0.4 },
    { form: marble, x: 0.14, y: 0.8, scale: 0.95, z: 0.8, minCount: 4, mix: 0.55 },
    { form: swatchFan, x: 0.5, y: 0.08, scale: 0.55, z: 0.45, minCount: 5, mix: 0.3 },
  ],
};

export const SIDE_ANGLE: Record<string, number> = {
  north: 0,
  east: Math.PI / 2,
  south: Math.PI,
  west: -Math.PI / 2,
};
