/**
 * ASCII background engine.
 *
 * Adapted from the ASCII "ocean" of the Kurage Dashboard template (HorizonX, licensed to
 * the Constriva owner through their membership): the same light-field -> monospace glyph
 * grid technique, tinted tiles, drifting dust, ripples, pointer reaction, typing boost and
 * mode palettes. The jellyfish are replaced by Constriva's architectural forms (forms.ts).
 *
 *   const ocean = new AsciiOcean(hostDiv, canvas);
 *   ocean.setTheme('blueprint'); ocean.setPlaying(true); ocean.resize();
 *   ocean.typing(); ocean.setWorking(true); ocean.pulse(); ocean.setFacing('east');
 *
 * Works as a no-op where canvas 2D is unavailable (tests, very old browsers).
 */
import { LAYOUTS, SIDE_ANGLE, type FormState, type Pen, type Placement, type Theme } from './forms';

type RGB = [number, number, number];
interface Palette {
  a: RGB;
  b: RGB;
  tempo: number;
}

const PALETTES: Record<Theme, Palette> = {
  blueprint: { a: [92, 226, 240], b: [124, 160, 255], tempo: 1 },
  brass: { a: [246, 198, 130], b: [222, 136, 80], tempo: 0.9 },
};
const DUST: Record<Theme, string> = { blueprint: '150,172,205', brass: '205,178,142' };
const ACCENTS: Record<Theme, string[]> = {
  blueprint: ['#f9a8d4', '#fcd34d', '#86efac', '#c4b5fd'],
  brass: ['#fde68a', '#fca5a5', '#a7f3d0', '#fdba74'],
};
const RAMP: [string, string][] = [
  ['.', ','], ["'", '`'], [':', "'"], [';', ':'], ['o', ';'], ['t', 'o'],
  ['%', 't'], ['S', '%'], ['X', 'S'], ['8', 'X'], ['@', '8'], ['#', '@'],
];
const SNOW = ['.', '.', '.', '-', '-', "'", ',', '·'];
const FONT = '"Geist Mono", "JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace';
const SS = 2; // offscreen samples per cell, per axis

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const clamp = (v: number, lo: number, hi: number) => (v < lo ? lo : v > hi ? hi : v);
const ease = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

function hash(x: number, y: number, t: number): number {
  let h = Math.imul(x, 374761393) ^ Math.imul(y, 668265263) ^ Math.imul(t, 1103515245);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}

interface Form {
  p: Placement;
  seed: number;
  ox: number;
  oy: number; // pointer push offset
  prims: number; // primitives drawn last full frame (for drafting)
  build: number; // 0..1 how much of the form is drawn
}
interface Dust {
  x: number;
  y: number;
  vx: number;
  vy: number;
  seed: number;
  g: string;
  run: number;
  a: number;
}
interface Ripple {
  x: number;
  y: number;
  t0: number;
  dur: number;
  max: number;
}

export class AsciiOcean {
  private ctx: CanvasRenderingContext2D | null;
  private off: HTMLCanvasElement;
  private octx: CanvasRenderingContext2D | null;
  private W = 0;
  private H = 0;
  private dpr = 1;
  private cw = 10;
  private ch = 15;
  private cols = 0;
  private rows = 0;
  private ow = 0;
  private oh = 0;
  private fs = 11;
  private forms: Form[] = [];
  private dust: Dust[] = [];
  private ripples: Ripple[] = [];
  private time = 0;
  private last = 0;
  private acc = 0;
  private raf = 0;
  private playing = true;
  private visible = typeof document === 'undefined' ? true : !document.hidden;
  private gain = 1;
  private typingUntil = 0;
  private boostUntil = 0;
  private flickerUntil = 0;
  private dimUntil = 0;
  private working = false;
  private theme: Theme = 'blueprint';
  private pal: Palette = { ...PALETTES.blueprint, a: [...PALETTES.blueprint.a], b: [...PALETTES.blueprint.b] };
  private palFrom: Palette | null = null;
  private palTo: Palette | null = null;
  private palT = 1;
  private palQ = -1;
  private needle = 0;
  private needleTarget = 0;
  private pointer = { x: -1e5, y: -1e5 };
  private target = { x: 0, y: 0 };
  private styles = new Map<number, { tile: string; glyph: string }>();
  private onVisibility = () => {
    this.visible = !document.hidden;
    this.sync();
  };

  private host: HTMLElement;
  private canvas: HTMLCanvasElement;

  constructor(host: HTMLElement, canvas: HTMLCanvasElement) {
    this.host = host;
    this.canvas = canvas;
    let ctx: CanvasRenderingContext2D | null = null;
    let octx: CanvasRenderingContext2D | null = null;
    this.off = document.createElement('canvas');
    try {
      ctx = canvas.getContext('2d');
      octx = this.off.getContext('2d', { willReadFrequently: true });
    } catch {
      ctx = null;
    }
    this.ctx = ctx;
    this.octx = octx;
    document.addEventListener('visibilitychange', this.onVisibility);
  }

  get supported(): boolean {
    return Boolean(this.ctx && this.octx);
  }

  destroy(): void {
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = 0;
    document.removeEventListener('visibilitychange', this.onVisibility);
  }

  // -------------------------------------------------------------- controls

  setTheme(theme: Theme): void {
    if (theme === this.theme && this.forms.length) return;
    const fresh = this.theme !== theme;
    this.theme = theme;
    const p = PALETTES[theme];
    if (!this.playing || !this.W || !fresh) {
      this.pal = { a: [...p.a], b: [...p.b], tempo: p.tempo };
      this.palT = 1;
    } else {
      this.palFrom = { a: [...this.pal.a], b: [...this.pal.b], tempo: this.pal.tempo };
      this.palTo = p;
      this.palT = 0;
      this.palQ = -1;
    }
    this.styles.clear();
    if (this.W) {
      this.seedForms();
      this.seedDust();
      this.render();
    }
  }

  setPlaying(on: boolean): void {
    this.playing = on;
    this.sync();
    if (!on) this.render();
  }

  isPlaying(): boolean {
    return this.playing;
  }

  setPointer(x: number, y: number): void {
    this.pointer.x = x;
    this.pointer.y = y;
  }

  setTarget(x: number, y: number): void {
    this.target.x = x;
    this.target.y = y;
  }

  /** The person is typing: forms brighten and move a little faster for a moment. */
  typing(): void {
    this.typingUntil = this.time + 1.8;
  }

  /** The AI is working: forms draw themselves in, line by line. */
  setWorking(on: boolean): void {
    if (on && !this.working) for (const f of this.forms) f.build = 0;
    this.working = on;
  }

  /** Something finished: a ripple from the composer and a bright flicker. */
  pulse(): void {
    if (!this.playing) return;
    this.boostUntil = this.time + 1.8;
    this.flickerUntil = this.time + 1.2;
    const m = Math.max(this.W, this.H);
    this.ripples.push({ x: this.target.x, y: this.target.y, t0: this.time, dur: 1.7, max: m * 0.62 });
    this.ripples.push({ x: this.target.x, y: this.target.y, t0: this.time + 0.26, dur: 1.7, max: m * 0.5 });
  }

  /** A mistake (empty prompt, error): the background dims briefly. */
  dim(): void {
    if (this.playing) this.dimUntil = this.time + 0.5;
  }

  /** The compass needle turns to the plan's facing side. */
  setFacing(side: string | null | undefined): void {
    if (!side || !(side in SIDE_ANGLE)) return;
    this.needleTarget = SIDE_ANGLE[side];
    if (!this.playing) {
      this.needle = this.needleTarget;
      this.render();
    }
  }

  redraw(): void {
    this.styles.clear();
    this.render();
  }

  // ------------------------------------------------------------------ setup

  resize(): void {
    if (!this.supported) return;
    const r = this.host.getBoundingClientRect();
    const nW = Math.max(1, Math.round(r.width)), nH = Math.max(1, Math.round(r.height));
    if (nW === this.W && nH === this.H) return;
    const first = !this.W;
    this.W = nW;
    this.H = nH;
    this.dpr = Math.min(2, window.devicePixelRatio || 1);
    this.cw = nW < 600 ? 8 : nW < 1100 ? 9 : 10;
    this.ch = Math.round(this.cw * 1.5);
    this.fs = Math.round(this.ch * 0.74);
    this.cols = Math.ceil(nW / this.cw);
    this.rows = Math.ceil(nH / this.ch);
    this.canvas.width = Math.round(nW * this.dpr);
    this.canvas.height = Math.round(nH * this.dpr);
    this.ow = this.cols * SS;
    this.oh = this.rows * SS;
    this.off.width = this.ow;
    this.off.height = this.oh;
    this.host.style.setProperty('--cw', `${this.cw}px`);
    this.host.style.setProperty('--ch', `${this.ch}px`);
    if (first || !this.forms.length) this.seedForms();
    else this.trimForms();
    this.seedDust();
    if (first) for (let i = 0; i < 30; i++) this.step(1 / 60);
    this.render();
    this.sync();
  }

  private formCount(): number {
    return this.W < 600 ? 3 : this.W < 1100 ? 4 : 5;
  }

  private seedForms(): void {
    const n = this.formCount();
    this.forms = LAYOUTS[this.theme]
      .filter((p) => p.minCount <= n)
      .map((p, i) => ({ p, seed: (i + 1) * 0.173, ox: 0, oy: 0, prims: 0, build: 1 }));
  }

  private trimForms(): void {
    const n = this.formCount();
    if (this.forms.length !== LAYOUTS[this.theme].filter((p) => p.minCount <= n).length) this.seedForms();
  }

  private seedDust(): void {
    this.dust = [];
    const n = Math.round((this.cols * this.rows) / 80);
    for (let i = 0; i < n; i++) {
      this.dust.push({
        x: Math.random() * this.W,
        y: Math.random() * this.H,
        vy: 3 + Math.random() * 8,
        vx: (Math.random() - 0.5) * 3,
        seed: Math.random() * 6.28,
        g: SNOW[(Math.random() * SNOW.length) | 0],
        run: Math.random() < 0.16 ? 2 + ((Math.random() * 3) | 0) : 1,
        a: 0.12 + Math.random() * 0.28,
      });
    }
  }

  private baseSize(): number {
    return clamp(Math.min(this.W, this.H * 1.25) * 0.12, 60, 150);
  }

  // ------------------------------------------------------------- simulation

  private step(dt: number): void {
    this.time += dt;
    const t = this.time;

    if (this.palT < 1 && this.palFrom && this.palTo) {
      this.palT = Math.min(1, this.palT + dt / 0.9);
      const q = Math.round(this.palT * 18);
      if (q !== this.palQ) {
        this.palQ = q;
        const e = ease(q / 18);
        const f = this.palFrom, to = this.palTo;
        this.pal = {
          a: f.a.map((v, i) => lerp(v, to.a[i], e)) as RGB,
          b: f.b.map((v, i) => lerp(v, to.b[i], e)) as RGB,
          tempo: lerp(f.tempo, to.tempo, e),
        };
        this.styles.clear();
      }
    }

    const typing = t < this.typingUntil;
    const boosting = t < this.boostUntil;
    const gTarget = t < this.dimUntil ? 0.3 : (typing ? 1.12 : 1) * (boosting ? 1.25 : 1) * (this.working ? 1.08 : 1);
    this.gain += (gTarget - this.gain) * Math.min(1, dt * (gTarget < this.gain ? 9 : 2.4));

    // compass needle: shortest turn to the target
    let d = this.needleTarget - this.needle;
    d = Math.atan2(Math.sin(d), Math.cos(d));
    this.needle += d * Math.min(1, dt * 1.6);

    const s0 = this.baseSize();
    for (const f of this.forms) {
      const size = s0 * f.p.scale;
      const cx = f.p.x * this.W, cy = f.p.y * this.H;
      const px = cx - this.pointer.x, py = cy - this.pointer.y;
      const pd = Math.hypot(px, py) || 1;
      const reach = size * 2.6;
      let tx = 0, ty = 0;
      if (pd < reach) {
        const push = (1 - pd / reach) * size * 0.28;
        tx = (px / pd) * push;
        ty = (py / pd) * push;
      }
      f.ox += (tx - f.ox) * Math.min(1, dt * 2.6);
      f.oy += (ty - f.oy) * Math.min(1, dt * 2.6);
      if (this.working) {
        f.build += dt * 0.42;
        if (f.build > 1.35) f.build = 0; // hold the finished drawing a moment, then redraw
      } else {
        f.build = Math.min(1, f.build + dt * 1.5);
      }
    }

    for (const s of this.dust) {
      s.y += s.vy * dt;
      s.x += (s.vx + Math.sin(t * 0.3 + s.seed) * 2) * dt;
      if (s.y > this.H + this.ch) {
        s.y = -this.ch;
        s.x = Math.random() * this.W;
      }
      if (s.x < -this.cw * 8) s.x += this.W + this.cw * 8;
      else if (s.x > this.W + this.cw) s.x -= this.W + this.cw * 8;
    }

    for (let i = this.ripples.length - 1; i >= 0; i--) {
      if (t - this.ripples[i].t0 > this.ripples[i].dur) this.ripples.splice(i, 1);
    }
  }

  // ------------------------------------------------- drawing: the light field

  /** Channels: R = hue A weight, B = hue B weight, G = white core. Additive. */
  private col(m: number, k: number, w: number): string {
    return `rgb(${Math.min(255, (1 - m) * k * 255) | 0},${Math.min(255, w * 255) | 0},${Math.min(255, m * k * 255) | 0})`;
  }

  private drawField(): void {
    const g = this.octx!;
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalCompositeOperation = 'source-over';
    g.fillStyle = '#000';
    g.fillRect(0, 0, this.ow, this.oh);
    g.setTransform(SS / this.cw, 0, 0, SS / this.ch, 0, 0);
    g.globalCompositeOperation = 'lighter';
    g.lineCap = 'round';
    g.lineJoin = 'round';

    for (const r of this.ripples) {
      const tt = (this.time - r.t0) / r.dur;
      if (tt < 0) continue;
      const rad = (1 - Math.pow(1 - tt, 3)) * r.max, fade = 1 - tt;
      g.lineWidth = 6 + 12 * fade;
      g.strokeStyle = this.col(0.5, 0.5 * fade, 0.55 * fade);
      g.beginPath();
      g.ellipse(r.x, r.y, rad, rad * 0.56, 0, 0, Math.PI * 2);
      g.stroke();
    }

    const boostT = this.time < this.boostUntil ? (this.boostUntil - this.time) / 1.8 : 0;
    const typing = this.time < this.typingUntil;
    const tempo = this.pal.tempo * (typing ? 1.3 : 1) * (this.working ? 1.25 : 1);
    const s0 = this.baseSize();
    for (const f of this.forms) {
      const size = s0 * f.p.scale;
      const t = this.time * tempo;
      const bx = f.p.x * this.W + Math.cos(t * 0.18 + f.seed * 9) * size * 0.05 + f.ox;
      const by = f.p.y * this.H + Math.sin(t * 0.25 + f.seed * 7) * size * 0.06 + f.oy;
      const pd = Math.hypot(bx - this.pointer.x, by - this.pointer.y);
      const near = pd < size * 2 ? (1 - pd / (size * 2)) * 0.35 : 0;
      const k = this.gain * 1.3 * (0.8 + 0.55 * f.p.z) * (1 + boostT * 0.6 + near);
      const m = f.p.mix;
      const limit = f.build >= 1 ? Infinity : Math.floor(f.prims * clamp(f.build, 0, 1));
      let count = 0;
      const pen: Pen = {
        g,
        col: (kk: number, w = 0) => this.col(m, kk, w),
        step: () => count++ < limit,
      };
      const st: FormState = { t, k, facing: this.needle, seed: f.seed };
      g.save();
      g.translate(bx, by);
      f.p.form.draw(pen, size, st);
      g.restore();
      if (f.build >= 1) f.prims = count;
    }
  }

  // --------------------------------------------------- drawing: glyph grid

  private style(tb: number, lv: number, wb: number) {
    const key = (tb * 12 + lv) * 3 + wb;
    const hit = this.styles.get(key);
    if (hit) return hit;
    const t = tb / 5, L = (lv + 0.5) / 12, w = [0, 0.3, 0.62][wb];
    const base = [0, 1, 2].map((i) => lerp(this.pal.a[i], this.pal.b[i], t));
    // Every lit cell is a tinted tile with a glyph on it; the hottest cells invert.
    const hot = lv >= 10 && wb > 0;
    const tileMix = hot ? 0.5 + w * 0.3 : 0;
    const tile = base.map((v) => lerp(v * 0.58, 236, tileMix) | 0);
    const mixW = clamp(0.12 + L * 0.5 + w * 0.34, 0, 0.94);
    const glyph = hot ? [6, 10, 16] : base.map((v) => lerp(v, 246, mixW) | 0);
    const s = {
      tile: `rgba(${tile[0]},${tile[1]},${tile[2]},${(hot ? 0.92 : 0.16 + L * 0.6).toFixed(3)})`,
      glyph: hot ? `rgb(${glyph.join(',')})` : `rgba(${glyph[0]},${glyph[1]},${glyph[2]},${(0.55 + L * 0.45).toFixed(3)})`,
    };
    this.styles.set(key, s);
    return s;
  }

  private render(): void {
    if (!this.W || !this.ctx || !this.octx) return;
    this.drawField();
    const d = this.octx.getImageData(0, 0, this.ow, this.oh).data;
    const ctx = this.ctx;
    const { cw, ch } = this;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.clearRect(0, 0, this.W, this.H);
    ctx.font = `500 ${this.fs}px ${FONT}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const ty = ch / 2 + 0.5, tx = cw / 2;

    const dust = DUST[this.theme];
    for (const s of this.dust) {
      const cx = Math.floor(s.x / cw), cy = Math.floor(s.y / ch);
      ctx.fillStyle = `rgba(${dust},${s.a.toFixed(3)})`;
      for (let r = 0; r < s.run; r++) ctx.fillText(s.run > 1 ? '-' : s.g, (cx + r * 2) * cw + tx, cy * ch + ty);
    }

    const accents = ACCENTS[this.theme];
    const tickRate = this.time < this.flickerUntil ? 10 : 1.4;
    const row = this.ow * 4;
    for (let cy = 0; cy < this.rows; cy++) {
      for (let cx = 0; cx < this.cols; cx++) {
        const i = (cy * SS * this.ow + cx * SS) * 4;
        const a = (d[i] + d[i + 4] + d[i + row] + d[i + row + 4]) / 1020;
        const w = (d[i + 1] + d[i + 5] + d[i + row + 1] + d[i + row + 5]) / 1020;
        const b = (d[i + 2] + d[i + 6] + d[i + row + 2] + d[i + row + 6]) / 1020;
        const L = Math.min(1, a + b + w * 0.55);
        if (L < 0.055) continue;
        const tb = Math.round((b / (a + b + 1e-4)) * 5);
        const lv = Math.min(11, (L * 12) | 0);
        const wb = w < 0.12 ? 0 : w < 0.32 ? 1 : 2;
        const st = this.style(tb, lv, wb);
        const x = cx * cw, y = cy * ch;
        if (lv >= 1) {
          ctx.fillStyle = st.tile;
          ctx.fillRect(x + 1, y + 1, cw - 2, ch - 2);
        }
        const tick = Math.floor(this.time * tickRate + ((cx * 7 + cy * 13) & 15) / 16);
        const h = hash(cx, cy, tick);
        ctx.fillStyle = lv >= 4 && lv < 10 && h > 0.986 ? accents[((h * 1e4) | 0) & 3] : st.glyph;
        ctx.fillText(RAMP[lv][h < 0.55 ? 0 : 1], x + tx, y + ty);
      }
    }
  }

  // ------------------------------------------------------------------ loop

  private loop = (now: number) => {
    this.raf = requestAnimationFrame(this.loop);
    if (!this.last) {
      this.last = now;
      return;
    }
    const dt = (now - this.last) / 1000;
    this.last = now;
    this.acc += Math.min(dt, 0.1);
    if (this.acc < 1 / 30) return;
    const n = Math.max(1, Math.min(6, Math.round(this.acc * 60))), h = this.acc / n;
    for (let i = 0; i < n; i++) this.step(h);
    this.acc = 0;
    this.render();
  };

  private sync(): void {
    const should = this.playing && this.visible && this.W > 0 && this.supported;
    if (should && !this.raf) {
      this.last = 0;
      this.raf = requestAnimationFrame(this.loop);
    } else if (!should && this.raf) {
      cancelAnimationFrame(this.raf);
      this.raf = 0;
    }
  }
}
