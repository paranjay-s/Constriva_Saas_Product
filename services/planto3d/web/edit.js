// Review screen: the plan drawn over the PDF page; fix walls / openings / room types, then build.
// The plan may come from the detector, from another reader (an AI plan reader, a floor plan generator: "imported"),
// or be traced here from nothing over the page image.
const $ = (id) => document.getElementById(id);
const job = new URLSearchParams(location.search).get('job');
// ?embed: framed by another site's page, which has its own build options and progress. This page then only reviews
// the plan, tells its host what happens (postMessage, source 'planto3d') and saves the plan when the host asks.
const EMBED = new URLSearchParams(location.search).has('embed') && parent !== window;
const tell = (m) => EMBED && parent.postMessage({ source: 'planto3d', job, ...m }, '*');
if (EMBED) document.body.classList.add('embed');
const cv = $('cv'), g = cv.getContext('2d');
const TYPES = ['bedroom', 'toilet', 'kitchen', 'living', 'dining', 'puja', 'wash', 'store', 'study', 'passage',
  'balcony', 'garden', 'open', 'parking', 'yard', 'stair', 'room', 'duct', 'dress'];
const ZCOL = { bedroom: '#c8a2c8', toilet: '#8fc7e8', kitchen: '#f2c48d', living: '#e9d48a', dining: '#e7b7a0', puja: '#f0a0a0',
  wash: '#a8d5c2', store: '#bbb', study: '#b8c9a0', passage: '#d9d2c3', balcony: '#b6dfa0', garden: '#7fc97f', open: '#9fd8d0',
  parking: '#c9c9d6', yard: '#cfe6b8', stair: '#c49a6c', room: '#dcdcdc', duct: '#999', dress: '#e3d2b8' };
const D = 100 / 72;          // page image px per PDF point
const FT_100 = 72 / 25.4 * 304.8 / 100;      // page points per foot at 1:100 (server.py FT_100)
// what each reader's plan needs checking for (the reader's own notice, from the server, follows)
const READERS = {
  ai: 'Read by the AI plan reader: check the walls, doors and sizes before you build.',
  stored: 'Opened from the floor plan generator: check the walls, doors and sizes before you build.',
  trace: 'This drawing could not be read automatically: trace the walls over it, set the scale, then add doors and windows.',
  manual: 'Drawn by hand: trace the walls over the drawing, set the scale, then add doors and windows.',
};
let plan, fi = 0, sel = null, tool = 'select', img = {}, history = [], pages = [];
let reader = '', notice = '', showBg = true, told, ready = false;
let view = { k: 10, ox: 40, oy: 600 };

// ---------------------------------------------------------------- loading / polling
async function poll() {
  const st = await fetch(`../api/jobs/${job}`).then((r) => r.json());
  $('title').textContent = st.name || 'Review';
  if (['uploaded', 'detecting'].includes(st.stage)) {
    $('wmsg').textContent = st.message || 'Reading the drawing…';
    $('wbar').style.width = (st.progress || 5) + '%';
    return setTimeout(poll, 700);
  }
  if (st.stage === 'failed' && !plan && !(st.floors || []).length) {      // the detection failed: there is no plan to show
    $('wmsg').textContent = st.message; $('wmsg').className = 'err'; $('back').hidden = false;
    return tell({ type: 'failed', message: st.message });
  }
  if (!plan) {
    await load(st);
    const why = problem();
    told = why; ready = true;
    tell({ type: 'ready', floors: plan.floors.length, reader, notice, buildable: !why, problem: why });
  }
  buildStatus(st);
}
async function load(st) {
  plan = await fetch(`../jobs/${job}/plan.json`).then((r) => r.json());
  reader = st.reader || 'detector'; notice = st.notice || ''; pages = st.pages || [];
  for (const f of plan.floors) for (const k of ['walls', 'openings', 'rooms', 'stairs', 'labels']) f[k] = f[k] || [];
  $('wait').style.display = 'none';
  const text = READERS[reader];
  if (text || notice) {               // (the framing page shows its own notice: see edit.html)
    $('ntext').textContent = text || '';
    $('nmore').textContent = notice;
    $('notice').hidden = false;
  }
  $('fh').value = plan.floor_height;
  $('furn').checked = plan.furnish !== false;
  if (pages.length > 1) for (const p of pages) $('bgpage').append(new Option(`Page ${p.n}`, p.n));
  $('bgpagerow').hidden = pages.length < 2;
  tabs();
  plan.floors.forEach((f) => { pageImage(bgPage(f)); guessBg(f); });
  plan.floors.forEach((f) => { if (f.auto_rooms && !f.rooms.length && f.walls.length) deriveRooms(f); });
  fit(); ui();
}
function tabs() {
  $('tabs').replaceChildren(...plan.floors.map((f, i) => {
    const b = document.createElement('button');
    b.textContent = f.name;
    b.onclick = () => { fi = i; sel = null; fit(); ui(); };
    return b;
  }));
}
function pageImage(p) {
  if (img[p]) return;
  const im = new Image();
  im.onload = () => { plan.floors.forEach(guessBg); if (plan.floors.some((f) => bgPage(f) === p)) fit(); ui(); };
  im.onerror = () => ui();
  im.src = `../jobs/${job}/page-${p}.png`;
  img[p] = im;
}
// playful words while Blender works, with the time left beside them
const WORDS = ['Raising walls', 'Laying bricks', 'Squaring corners', 'Hanging doors', 'Polishing windows', 'Pouring floors',
  'Mixing paint', 'Tiling bathrooms', 'Measuring twice', 'Switching on lamps', 'Chasing shadows', 'Baking sunlight', 'Sweeping up'];
const FURNISHED = ['Fluffing pillows', 'Arranging furniture', 'Watering plants', 'Making the beds'];
let fun = null;
function funWords(on) {
  $('bfun').hidden = !on;
  if (on === !!fun) return;
  if (!on) { clearInterval(fun); fun = null; return; }
  const words = $('furn').checked ? WORDS.concat(FURNISHED) : WORDS;
  const next = () => {           // never the same word twice in a row
    let w;
    do w = words[Math.floor(Math.random() * words.length)] + '…'; while (w === $('bword').textContent);
    $('bword').textContent = w;
  };
  next();
  fun = setInterval(next, 2800);
}
const secs = (s) => (s >= 90 ? `${Math.round(s / 60)} min` : `${s} s`);
function buildStatus(st) {
  if (!['queued', 'building', 'done', 'failed'].includes(st.stage)) return;
  $('buildbox').hidden = false;
  $('bbar').style.width = (st.progress || 0) + '%';
  funWords(['queued', 'building'].includes(st.stage));
  const left = st.stage === 'building' ? st.eta_left : null;      // seconds, estimated from earlier builds on this machine
  $('beta').textContent = left == null ? '' : left > 8 ? `about ${secs(left >= 90 ? left : Math.ceil(left / 5) * 5)} left` : 'almost done';
  const took = st.stage === 'done' && st.build_seconds ? `built in ${secs(st.build_seconds)}` : '';
  const step = st.stage === 'building' && !/cooling/.test(st.message) ? '' : st.message;     // Blender's step names stay out of sight
  $('bmsg').textContent = st.stage === 'failed' ? `Failed: ${st.message}` : [step, took].filter(Boolean).join(' · ');
  $('bmsg').className = st.stage === 'failed' ? 'err' : 'muted';
  $('open').hidden = st.stage !== 'done';
  $('open').href = `view.html?job=${job}`;
  $('build').disabled = ['queued', 'building'].includes(st.stage);
  if (['queued', 'building'].includes(st.stage)) setTimeout(() => fetch(`../api/jobs/${job}`).then((r) => r.json()).then(buildStatus), 1500);
}

// ---------------------------------------------------------------- geometry helpers
const F = () => plan.floors[fi];
const toC = (x, y) => [view.ox + x * view.k, view.oy - y * view.k];
const toP = (X, Y) => [(X - view.ox) / view.k, (view.oy - Y) / view.k];
const inR = (r, x, y, m = 0) => x >= r[0] - m && x <= r[1] + m && y >= r[2] - m && y <= r[3] + m;
const horiz = (r) => r[1] - r[0] >= r[3] - r[2];
const area = (r) => (r[1] - r[0]) * (r[3] - r[2]);
const r3 = (v) => +v.toFixed(3);
function bboxOf(rs) {
  return rs.length ? [Math.min(...rs.map((r) => r[0])), Math.max(...rs.map((r) => r[1])),
    Math.min(...rs.map((r) => r[2])), Math.max(...rs.map((r) => r[3]))] : null;
}
// what is drawn on a floor (walls, else rooms), or null for a floor with nothing on it yet
const drawn = (f) => bboxOf(f.walls.length ? f.walls : f.rooms.flatMap((z) => z.rects));
function fit() {
  const f = F(), b = drawn(f) || pageRect(f) || [0, f.size?.[0] || 40, 0, f.size?.[1] || 30];
  const W = cv.clientWidth, H = cv.clientHeight, w = b[1] - b[0], h = b[3] - b[2];
  view.k = Math.min((W - 60) / w, (H - 60) / h);
  view.ox = (W - w * view.k) / 2 - b[0] * view.k;
  view.oy = (H + h * view.k) / 2 + b[2] * view.k;
  draw();
}
function wallT(f = F()) {
  const t = f.walls.map((w) => Math.min(w[1] - w[0], w[3] - w[2])).sort((a, b) => a - b);
  return t[Math.floor(t.length / 2)] || (plan.wall_pt && plan.scale_pt_per_ft ? plan.wall_pt / plan.scale_pt_per_ft : 0.75);
}
function snapshot() { history.push(JSON.stringify(plan)); if (history.length > 50) history.shift(); }

// ---------------------------------------------------------------- the page image under a floor
// A floor's `bg` says where it lies on its page image: page (1-based), rot (the image turned clockwise by 0/90/180/270),
// pt_per_ft and origin_pt (the turned page's point, in PDF points from its top-left corner with y down, where plan
// (0, 0) lies; plan y runs up the page) and fit (given / matched / guess). Without `bg`, a detector plan lies where
// the detector found it: origin_pt of the floor and the plan's scale_pt_per_ft.
function bgOf(f) {
  const b = f.bg || {}, page = b.page || f.page || 1, rot = b.rot || 0;
  if (b.pt_per_ft && b.origin_pt) return { page, rot, s: b.pt_per_ft, o: b.origin_pt, fit: b.fit || 'given' };
  if (f.origin_pt && plan.scale_pt_per_ft) return { page, rot, s: plan.scale_pt_per_ft, o: f.origin_pt, fit: 'given' };
  return null;
}
const bgPage = (f) => f.bg?.page || f.page || 1;
const setBg = (f, b) => { f.bg = { page: b.page, rot: b.rot, pt_per_ft: +b.s.toFixed(5), origin_pt: b.o.map((v) => +v.toFixed(3)), fit: b.fit }; };
// size of the page image in points, turned as the floor shows it
function pageSize(p, rot) {
  const im = img[p], known = pages.find((q) => q.n === p);
  const s = im?.naturalWidth ? [im.naturalWidth / D, im.naturalHeight / D] : known ? [known.w, known.h] : null;
  return s && (rot % 180 ? [s[1], s[0]] : s);
}
const pagePt = (b, x, y) => [b.o[0] + x * b.s, b.o[1] - y * b.s];
const planPt = (b, u, v) => [(u - b.o[0]) / b.s, (b.o[1] - v) / b.s];
function pageRect(f) {          // the page's outline in the floor's plan coordinates
  const b = bgOf(f), s = b && pageSize(b.page, b.rot);
  if (!s) return null;
  const [x0, y1] = planPt(b, 0, 0), [x1, y0] = planPt(b, s[0], s[1]);
  return [x0, x1, y0, y1];
}
// a plan not read from the PDF's own drawing (AI, generator) is not lined up with it: until the person lines it up,
// its page is laid under it centred and big enough, once (it must not move when walls change)
function guessFor(f, page, rot) {
  const s = pageSize(page, rot), b = drawn(f);
  if (!s) return null;
  if (!b) return { page, rot, s: plan.scale_pt_per_ft || FT_100, o: [0, s[1]], fit: 'guess' };
  const k = 0.85 * Math.min(s[0] / Math.max(b[1] - b[0], 1), s[1] / Math.max(b[3] - b[2], 1));
  return { page, rot, s: k, o: [s[0] / 2 - (b[0] + b[1]) / 2 * k, s[1] / 2 + (b[2] + b[3]) / 2 * k], fit: 'guess' };
}
function guessBg(f) {
  const b = !bgOf(f) && guessFor(f, bgPage(f), f.bg?.rot || 0);
  if (b) setBg(f, b);
}
function drawPage(f) {
  const b = bgOf(f), im = b && img[b.page];
  if (!showBg || !im?.complete || !im.naturalWidth) return;
  const c = view.k / b.s, w = im.naturalWidth, h = im.naturalHeight;
  g.save();
  g.globalAlpha = 0.45;
  g.translate(view.ox - b.o[0] * c, view.oy - b.o[1] * c);
  g.scale(c / D, c / D);
  if (b.rot === 90) { g.translate(h, 0); g.rotate(Math.PI / 2); }
  else if (b.rot === 180) { g.translate(w, h); g.rotate(Math.PI); }
  else if (b.rot === 270) { g.translate(0, w); g.rotate(-Math.PI / 2); }
  g.drawImage(im, 0, 0);
  g.restore();
}
// turn the page under the floor by a quarter; the plan point at the page's centre stays put
function turnBg(d) {
  const f = F();
  guessBg(f);
  const b = bgOf(f) || { page: bgPage(f), rot: 0, s: plan.scale_pt_per_ft || FT_100, o: [0, 0], fit: 'guess' };
  const s0 = pageSize(b.page, b.rot), rot = (b.rot + d + 360) % 360, s1 = pageSize(b.page, rot);
  if (!s0) return;
  snapshot();
  const c = planPt(b, s0[0] / 2, s0[1] / 2);
  const empty = !f.walls.length && !f.rooms.length;
  const o = empty ? [0, s1[1]] : [s1[0] / 2 - c[0] * b.s, s1[1] / 2 + c[1] * b.s];
  setBg(f, { ...b, rot, o, fit: b.fit === 'guess' ? 'guess' : 'matched' });
  if (empty) f.size = [r3(s1[0] / b.s), r3(s1[1] / b.s)];
  pairs = []; pending = null;
  fit(); ui();
}
function pickPage(p) {          // the floor is on another page: start it at that page's corner, or centred on it
  const f = F(), b = bgOf(f), rot = b?.rot || 0, s = pageSize(p, rot);
  if (!s) return;
  snapshot();
  setBg(f, b && !drawn(f) ? { page: p, rot, s: b.s, o: [0, s[1]], fit: b.fit } : guessFor(f, p, rot));
  pageImage(p);
  pairs = []; pending = null;
  fit(); ui();
}

// ---------------------------------------------------------------- drawing
function rectC(r) { const [a, b] = toC(r[0], r[3]), [c, d] = toC(r[1], r[2]); return [a, b, c - a, d - b]; }
// floor j's plan coordinates -> the current floor's, when both lie on the same page image at the same scale
function offsetOf(j) {
  const a = bgOf(F()), b = bgOf(plan.floors[j]);
  if (!a || !b || a.page !== b.page || a.rot !== b.rot || Math.abs(a.s - b.s) > 1e-3 * a.s) return null;
  return [(b.o[0] - a.o[0]) / a.s, (a.o[1] - b.o[1]) / a.s];
}
function drawFloor(f, dx, dy, active) {
  const fade = active ? 1 : 0.4, mv = (r) => [r[0] + dx, r[1] + dx, r[2] + dy, r[3] + dy];
  const isSel = (kind, i) => active && sel?.kind === kind && sel.i === i;
  f.rooms.forEach((z, i) => {
    g.fillStyle = ZCOL[z.type] || '#ddd';
    g.globalAlpha = (isSel('room', i) ? 0.75 : 0.38) * fade;
    z.rects.forEach((r) => g.fillRect(...rectC(mv(r))));
  });
  g.globalAlpha = fade;
  (f.stairs || []).forEach((st, i) => {
    g.fillStyle = isSel('stair', i) ? 'rgba(80,45,10,.8)' : 'rgba(138,90,43,.55)';
    g.fillRect(...rectC(mv(st.rect)));
    const up = (st.words || []).find((w) => /^UP/i.test(w[0]));
    if (up && active) { const [x, y] = toC(up[1] + dx, up[2] + dy); g.fillStyle = '#5a3510'; g.font = 'bold 11px system-ui'; g.textAlign = 'center'; g.fillText('UP', x, y); }
  });
  f.walls.forEach((w, i) => {
    g.fillStyle = isSel('wall', i) ? '#000' : w[4] ? '#d81bd8' : '#e53935';
    g.fillRect(...rectC(mv(w)));
  });
  const OC = { door: '#2e9d3a', window: '#1e6fe0', opening: '#f2b400' };
  f.openings.forEach((o, i) => {
    g.fillStyle = isSel('opening', i) ? '#000' : OC[o.type];
    const [x, y, w, h] = rectC(mv(o.rect));
    g.fillRect(x - 1, y - 1, w + 2, h + 2);
  });
  g.font = '12px system-ui'; g.textAlign = 'center';
  f.rooms.forEach((z) => {
    const r = mv(z.rects.reduce((a, b) => (area(b) > area(a) ? b : a)));
    if ((r[1] - r[0]) * view.k < 30) return;
    const [x, y] = toC((r[0] + r[1]) / 2, (r[2] + r[3]) / 2);
    g.fillStyle = '#111';
    g.fillText(z.type, x, y);
  });
  g.globalAlpha = 1;
}
function dot(x, y, col) { const [X, Y] = toC(x, y); g.fillStyle = col; g.beginPath(); g.arc(X, Y, 5, 0, 7); g.fill(); }
function draw() {
  if (!plan) return;
  const dpr = devicePixelRatio || 1;
  cv.width = cv.clientWidth * dpr; cv.height = cv.clientHeight * dpr;
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, cv.clientWidth, cv.clientHeight);
  const f = F();
  drawPage(f);
  // the other plans on this sheet stay visible (faded); click one to edit it
  plan.floors.forEach((o, j) => { const d = j !== fi && offsetOf(j); if (d) drawFloor(o, ...d, false); });
  drawFloor(f, 0, 0, true);
  if (drag?.preview) { g.strokeStyle = '#000'; g.setLineDash([4, 3]); g.strokeRect(...rectC(drag.preview)); g.setLineDash([]); }
  for (const p of scalePts) dot(...p, '#b0562b');
  const b = bgOf(f);
  if (b && pending) dot(...planPt(b, ...pending), '#e67e00');
  for (const [, q] of pairs) dot(...q, '#1e6fe0');
}

// ---------------------------------------------------------------- what the build needs
// gen.py takes each storey's outline from its walls and lays floors, lamps and furniture per room. A traced plan is
// at 1:100 until its scale is set, which is rarely right.
function problem() {
  if (!plan) return 'The plan is not loaded yet.';
  for (const f of plan.floors) {
    if (!f.walls.length) return `${f.name} has no walls yet: draw them first.`;
    const b = drawn(f), side = Math.max(b[1] - b[0], b[3] - b[2]);
    if (side < 8 || side > 600) return `${f.name} is ${side.toFixed(0)} ft across: set the scale (Set scale, then two points a known distance apart).`;
  }
  if (!plan.floors.some((f) => f.rooms.length)) return 'There are no rooms yet: close the walls around each room (rooms are found between walls, doors and windows).';
  if (['trace', 'manual'].includes(reader) && plan.scale_source === 'assumed') return 'Set the scale first: Set scale, then click two points a known distance apart.';
  return null;
}
function checkBuildable() {
  const why = problem();
  $('why').textContent = why ? `Before you build: ${why}` : '';
  $('why').hidden = !why;
  if (EMBED && ready && why !== told) { told = why; tell({ type: 'buildable', buildable: !why, problem: why }); }
  return why;
}

// ---------------------------------------------------------------- rooms from the walls
// As the detector finds them: the free space between walls, doors and windows, flood-filled on a grid; each closed
// region is a room made of a few rectangles. A room keeps the type and name of the room it mostly covers.
function deriveRooms(f) {
  const old = f.rooms;
  if (!f.walls.length) { f.rooms = []; return; }
  const T = wallT(f), bb = bboxOf(f.walls);
  const C = Math.max(0.25, Math.sqrt((bb[1] - bb[0] + 2 * T) * (bb[3] - bb[2] + 2 * T) / 4e5));
  const ox = bb[0] - T - C, oy = bb[2] - T - C;
  const nx = Math.ceil((bb[1] + T + C - ox) / C) + 1, ny = Math.ceil((bb[3] + T + C - oy) / C) + 1;
  const grid = new Uint8Array(nx * ny), lab = new Int32Array(nx * ny);
  const block = (r) => {
    const i0 = Math.max(0, Math.floor((r[0] - ox) / C)), i1 = Math.min(nx - 1, Math.floor((r[1] - ox) / C));
    const j0 = Math.max(0, Math.floor((r[2] - oy) / C)), j1 = Math.min(ny - 1, Math.floor((r[3] - oy) / C));
    for (let j = j0; j <= j1; j++) grid.fill(1, j * nx + i0, j * nx + i1 + 1);
  };
  f.walls.forEach(block);
  f.openings.filter((o) => o.type !== 'opening').forEach((o) => block(o.rect));      // (an opening joins two rooms)
  const regions = [];
  for (let s = 0; s < nx * ny; s++) {
    if (grid[s] || lab[s]) continue;
    const id = regions.length + 1, cells = [s], stack = [s];
    lab[s] = id;
    while (stack.length) {
      const c = stack.pop(), i = c % nx, j = (c - i) / nx;
      for (const [a, b] of [[i + 1, j], [i - 1, j], [i, j + 1], [i, j - 1]]) {
        if (a < 0 || b < 0 || a >= nx || b >= ny) continue;
        const n = b * nx + a;
        if (!grid[n] && !lab[n]) { lab[n] = id; stack.push(n); cells.push(n); }
      }
    }
    regions.push(cells);
  }
  const rooms = [];
  regions.forEach((cells, k) => {
    if (k + 1 === lab[0] || cells.length * C * C < 2) return;      // outside the house, or a sliver
    // rows of cells -> runs; equal runs on consecutive rows -> one rectangle
    const rows = new Map();
    for (const c of cells) { const i = c % nx, j = (c - i) / nx; (rows.get(j) || rows.set(j, []).get(j)).push(i); }
    const rects = [];
    let open = new Map();
    for (const j of [...rows.keys()].sort((a, b) => a - b)) {
      const xs = rows.get(j).sort((a, b) => a - b), runs = [];
      let a = xs[0];
      for (let n = 1; n <= xs.length; n++) if (n === xs.length || xs[n] !== xs[n - 1] + 1) { runs.push(`${a},${xs[n - 1]}`); a = xs[n]; }
      const next = new Map();
      for (const run of runs) next.set(run, open.has(run) && open.get(run)[1] === j - 1 ? [open.get(run)[0], j] : [j, j]);
      for (const [run, [j0, j1]] of open) if (!next.has(run) || next.get(run)[0] !== j0) rects.push([run, j0, j1]);
      open = next;
    }
    for (const [run, [j0, j1]] of open) rects.push([run, j0, j1]);
    const rs = rects.map(([run, j0, j1]) => { const [a, b] = run.split(',').map(Number); return [r3(ox + a * C), r3(ox + (b + 1) * C), r3(oy + j0 * C), r3(oy + (j1 + 1) * C)]; });
    const a = cells.length * C * C;
    const cover = (z) => z.rects.reduce((s, q) => s + rs.reduce((t, r) => t + Math.max(0, Math.min(q[1], r[1]) - Math.max(q[0], r[0])) * Math.max(0, Math.min(q[3], r[3]) - Math.max(q[2], r[2])), 0), 0);
    let best = null, most = 0;
    for (const z of old) { const c = cover(z); if (c > most) { most = c; best = z; } }
    const was = best && most > 0.25 * Math.min(a, z0area(best)) ? best : null;
    const stair = f.stairs.some((s) => rs.some((r) => inR(r, (s.rect[0] + s.rect[1]) / 2, (s.rect[2] + s.rect[3]) / 2)));
    rooms.push({ type: was ? was.type : stair ? 'stair' : a < 12 ? 'duct' : 'room', label: was?.label || '',
      dims: was?.dims || null, area: +a.toFixed(1), rects: rs });
  });
  f.rooms = rooms;
}
const z0area = (z) => z.rects.reduce((s, r) => s + area(r), 0);
const edited = (f = F()) => { if (f.auto_rooms) deriveRooms(f); };

// ---------------------------------------------------------------- side panel
const el = (tag, props = {}, ...kids) => { const e = Object.assign(document.createElement(tag), props); e.append(...kids); return e; };
const row = (...kids) => el('div', { className: 'row' }, ...kids);
const num = (id, value, step, w = 70) => el('input', { type: 'number', id, value, step, style: `width:${w}px` });
function ui() {
  if (!plan) return;
  document.querySelectorAll('#tabs button').forEach((b, i) => b.classList.toggle('on', i === fi));
  const f = F();
  $('fname').value = f.name;
  $('scale').textContent = `${plan.floors.length} floor${plan.floors.length > 1 ? 's' : ''} · scale ${{ labels: 'read from room sizes',
    user: 'set by hand', given: 'given by the plan reader' }[plan.scale_source] || 'GUESSED - use Set scale'}`;
  $('autorooms').checked = !!f.auto_rooms;
  $('delfloor').hidden = plan.floors.length < 2;
  const b = bgOf(f);
  $('bgstate').textContent = !b || !img[b.page]?.naturalWidth ? 'This page has no image to show.'
    : { given: 'Lined up with the PDF.', matched: 'Lined up by hand.', guess: 'Not lined up with the plan: use Line up.' }[b.fit];
  $('bgstate').className = b?.fit === 'guess' ? 'warn' : 'muted';
  if (b) $('bgpage').value = b.page;
  toolOpts();
  checkBuildable();
  const P = $('props');
  P.replaceChildren();
  if (!sel) {
    P.append(el('h3', { textContent: 'Selection' }), el('p', { className: 'muted', style: 'font-size:13px',
      textContent: `${f.walls.length} walls, ${f.openings.length} openings, ${f.rooms.length} rooms, ${f.stairs.length} stair flights` }));
    return draw();
  }
  const del = () => { snapshot(); remove(f, sel); sel = null; edited(f); ui(); };
  if (sel.kind === 'wall') {
    const w = f.walls[sel.i], h = horiz(w), len = h ? w[1] - w[0] : w[3] - w[2], t = h ? w[3] - w[2] : w[1] - w[0];
    const wl = el('select', { id: 'wl' }, new Option('Full height', 0), new Option('Low / parapet', 1));
    P.append(el('h3', { textContent: 'Wall' }), row(el('span', { textContent: `${len.toFixed(1)} ft long` }), wl),
      row(el('span', { textContent: 'Thickness (in)' }), num('wt', +(t * 12).toFixed(1), 0.5)),
      el('p', { className: 'muted', style: 'font-size:12px', textContent: 'Drag the wall to move it, or an end to lengthen it.' }));
    wl.value = w[4]; wl.onchange = (e) => { snapshot(); w[4] = +e.target.value; draw(); };
    $('wt').onchange = (e) => {
      const v = +e.target.value / 12;
      if (!(v >= 0.1 && v <= 3)) return;
      snapshot();
      const c = h ? (w[2] + w[3]) / 2 : (w[0] + w[1]) / 2, i = h ? 2 : 0;
      w[i] = r3(c - v / 2); w[i + 1] = r3(c + v / 2);
      for (const o of f.openings) if (overlaps(o.rect, w)) { o.rect[i] = w[i]; o.rect[i + 1] = w[i + 1]; }
      edited(f); ui();
    };
  } else if (sel.kind === 'opening') {
    const o = f.openings[sel.i], along = o.axis === 'x' ? 0 : 2;
    const ot = el('select', { id: 'ot' }, ...['door', 'window', 'opening'].map((t) => new Option(t, t)));
    P.append(el('h3', { textContent: 'Opening' }), row(el('span', { textContent: 'Type' }), ot),
      row(el('span', { textContent: 'Width (ft)' }), num('ow', +(o.rect[along + 1] - o.rect[along]).toFixed(2), 0.25)));
    ot.value = o.type; ot.onchange = (e) => { snapshot(); o.type = e.target.value; edited(f); ui(); };
    $('ow').onchange = (e) => {
      const v = +e.target.value;
      if (!(v >= 1 && v <= 30)) return;
      snapshot();
      const c = (o.rect[along] + o.rect[along + 1]) / 2;
      o.rect[along] = r3(c - v / 2); o.rect[along + 1] = r3(c + v / 2);
      if (o.hinge) delete o.hinge;
      edited(f); ui();
    };
  } else if (sel.kind === 'room') {
    const z = f.rooms[sel.i];
    const rt = el('select', { id: 'rt' }, ...TYPES.map((t) => new Option(t, t)));
    const rl = el('input', { type: 'text', id: 'rl', style: 'width:160px', value: z.label || '' });
    P.append(el('h3', { textContent: 'Room' }), row(el('span', { textContent: 'Type' }), rt),
      el('div', { className: 'row', style: 'margin-top:6px' }, el('span', { textContent: 'Label' }), rl),
      el('p', { className: 'muted', style: 'font-size:12px', textContent: `${+z.area} sq ft. Furniture follows the type.` }));
    rt.value = z.type; rt.onchange = (e) => { snapshot(); z.type = e.target.value; draw(); };
    rl.oninput = (e) => { z.label = e.target.value.slice(0, 80); };
  } else if (sel.kind === 'stair') {
    const s = f.stairs[sel.i];
    P.append(el('h3', { textContent: 'Stair flight' }),
      row(el('span', { textContent: `Climbs along ${s.axis}` }), el('span', {}, 'Steps ', num('ss', s.steps, 1, 56))),
      // room for the stair's own controls (its direction, for one), kept apart from the generic panel
      el('div', { id: 'stairctl' }));
    $('ss').onchange = (e) => { const v = Math.round(+e.target.value); if (v >= 3 && v <= 30) { snapshot(); s.steps = v; } };
  }
  if (sel.kind !== 'room') P.append(el('button', { className: 'btn ghost', textContent: 'Delete', style: 'margin-top:8px', onclick: del }));
  draw();
}
$('fname').oninput = (e) => { F().name = e.target.value.slice(0, 60); document.querySelectorAll('#tabs button')[fi].textContent = F().name; };
$('fh').onchange = (e) => { plan.floor_height = Math.max(8, Math.min(14, +e.target.value || 10)); };
$('autorooms').onchange = (e) => { snapshot(); F().auto_rooms = e.target.checked; edited(); ui(); };
$('findrooms').onclick = () => { snapshot(); deriveRooms(F()); sel = null; ui(); };
$('showbg').onchange = (e) => { showBg = e.target.checked; draw(); };
$('turnl').onclick = () => turnBg(-90);
$('turnr').onclick = () => turnBg(90);
$('bgpage').onchange = (e) => pickPage(+e.target.value);
$('addfloor').onclick = () => {          // a storey on top: traced over the same page until moved to another
  snapshot();
  const f = F(), n = plan.floors.length;
  plan.floors.push({ title: null, name: `Floor ${n}`, level: n, page: f.page || 1, origin_pt: f.origin_pt, size: f.size,
    ...(f.bg ? { bg: { ...f.bg } } : {}), auto_rooms: true, walls: [], openings: [], rooms: [], stairs: [], labels: [] });
  fi = n; sel = null; tabs(); fit(); ui();
};
$('delfloor').onclick = (e) => {        // a second click removes it: one click must not lose a storey's work
  if (plan.floors.length < 2) return;
  if (e.target.dataset.sure !== String(fi)) { e.target.dataset.sure = fi; e.target.textContent = 'Click again to remove'; return; }
  delete e.target.dataset.sure; e.target.textContent = 'Remove this floor';
  snapshot();
  plan.floors.splice(fi, 1);
  plan.floors.forEach((f, i) => { f.level = i; });
  fi = Math.min(fi, plan.floors.length - 1); sel = null; tabs(); fit(); ui();
};
function remove(f, s) {
  if (s.kind === 'wall') {               // its doors and windows go with it, unless another wall holds them
    const w = f.walls[s.i];
    f.openings = f.openings.filter((o) => !overlaps(o.rect, w) || f.walls.some((q) => q !== w && overlaps(o.rect, q)));
    f.walls.splice(s.i, 1);
  } else f[{ opening: 'openings', stair: 'stairs' }[s.kind]].splice(s.i, 1);
}
const overlaps = (a, b) => a[0] < b[1] && b[0] < a[1] && a[2] < b[3] && b[2] < a[3];

// ---------------------------------------------------------------- tools
const HINT = {
  select: 'Click a wall, opening, stair or room to edit it, or another floor plan to switch to it. Drag to pan, scroll to zoom.',
  wall: 'Drag along the line of the new wall. It runs straight across or up, and its ends meet the walls they touch.',
  door: 'Click on a wall where the door should be.',
  window: 'Click on a wall where the window should be.',
  stair: 'Drag over the stair flight, starting at its bottom step.',
  scale: 'Click two points a known distance apart, then type that distance.',
  lineup: 'Line up the drawing: click a point on the drawing, then the same point on the plan. Do it for two points far apart.',
};
let scalePts = [], pairs = [], pending = null, wallIn = null, widths = { door: 3, window: 4 };
document.querySelectorAll('#tools button[data-t]').forEach((b) => b.onclick = () => setTool(b.dataset.t));
function setTool(t) {
  tool = t; scalePts = []; pairs = []; pending = null;
  document.querySelectorAll('#tools button[data-t]').forEach((x) => x.classList.toggle('on', x.dataset.t === t));
  $('hint').textContent = HINT[tool];
  ui();
}
function toolOpts() {          // the active tool's settings, under the tool buttons
  const o = $('topts');
  if (o.dataset.tool === tool && tool !== 'scale') return;
  o.dataset.tool = tool;
  o.replaceChildren();
  if (tool === 'wall') {
    const t = num('wthick', wallIn ?? +(wallT() * 12).toFixed(1), 0.5);
    t.onchange = (e) => { const v = +e.target.value; if (v >= 1 && v <= 36) wallIn = v; };
    o.append(row(el('span', { textContent: 'Thickness (in)' }), t));
  } else if (tool === 'door' || tool === 'window') {
    const w = num('owidth', widths[tool], 0.25);
    w.onchange = (e) => { const v = +e.target.value; if (v >= 1 && v <= 30) widths[tool] = v; };
    o.append(row(el('span', { textContent: 'Width (ft)' }), w));
  } else if (tool === 'scale' && scalePts.length === 2) {
    const meas = Math.hypot(scalePts[1][0] - scalePts[0][0], scalePts[1][1] - scalePts[0][1]);
    const d = el('input', { type: 'text', id: 'sdist', placeholder: `12'6" or 3.8 m`, style: 'width:120px' });
    const go = el('button', { className: 'btn', id: 'sset', textContent: 'Set' });
    const msg = el('p', { className: 'muted', id: 'smsg', style: 'font-size:12px;margin:4px 0 0',
      textContent: `${meas.toFixed(2)} ft on the drawing now. Real distance: feet and inches (12'6"), or metres / centimetres (3.8 m, 380 cm).` });
    const apply = () => {
      const real = parseLength(d.value);
      if (!(real > 0) || !(meas > 0)) { msg.textContent = 'Type a distance such as 12\'6", 12.5 ft, 3.8 m or 380 cm.'; msg.className = 'err'; return; }
      scalePts = []; rescale(real / meas); setTool('select'); fit();
    };
    go.onclick = apply; d.onkeydown = (e) => { if (e.key === 'Enter') apply(); };
    o.append(row(d, go), msg);
    setTimeout(() => d.focus());
  } else if (tool === 'lineup') {
    o.append(el('button', { className: 'btn ghost', textContent: 'Start again', onclick: () => { pairs = []; pending = null; $('hint').textContent = HINT.lineup; draw(); } }));
  }
}
$('undo').onclick = () => {
  if (!history.length) return;
  const n = plan.floors.length;
  plan = JSON.parse(history.pop()); sel = null;
  if (plan.floors.length !== n) { fi = Math.min(fi, plan.floors.length - 1); tabs(); }
  ui();
};
addEventListener('keydown', (e) => {
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;
  if ((e.key === 'Delete' || e.key === 'Backspace') && sel && sel.kind !== 'room') { snapshot(); remove(F(), sel); sel = null; edited(); ui(); }
  if (e.key === 'Escape') { scalePts = []; pairs = []; pending = null; drag = null; toolOpts(); draw(); }
  if (e.key === 'z' && (e.ctrlKey || e.metaKey)) $('undo').onclick();
});

function pick(x, y) {
  const f = F(), m = 4 / view.k;
  let i = f.openings.findIndex((o) => inR(o.rect, x, y, m));
  if (i >= 0) return { kind: 'opening', i };
  i = f.walls.findIndex((w) => inR(w, x, y, m));
  if (i >= 0) return { kind: 'wall', i };
  i = (f.stairs || []).findIndex((s) => inR(s.rect, x, y));
  if (i >= 0) return { kind: 'stair', i };
  i = f.rooms.findIndex((z) => z.rects.some((r) => inR(r, x, y)));
  if (i >= 0) return { kind: 'room', i };
  return null;
}
// a typed distance -> feet. 12'6", 12' 6, 12'-6", 12 6, 12.5', 12.5 ft, 150", 3.8 m, 3,8 m, 380 cm, 3800 mm; a bare number is feet
function parseLength(s) {
  s = String(s || '').trim().toLowerCase().replace(/[’′]/g, "'").replace(/[”″]/g, '"').replace(/''/g, '"');
  let m = /^(\d+(?:[.,]\d+)?)\s*(mm|cm|m|metres?|meters?)$/.exec(s);
  if (m) return +m[1].replace(',', '.') / (m[2] === 'mm' ? 304.8 : m[2] === 'cm' ? 30.48 : 0.3048);
  m = /^(\d+(?:\.\d+)?)\s*(?:"|in|inch|inches)$/.exec(s);
  if (m) return +m[1] / 12;
  m = /^(\d+(?:\.\d+)?)\s*(?:'|ft|feet|foot)\s*-?\s*(?:(\d+(?:\.\d+)?)\s*(?:"|in|inch|inches)?)?$/.exec(s)
    || /^(\d+)(?:\s+|\s*-\s*)(\d+(?:\.\d+)?)$/.exec(s) || /^(\d+(?:\.\d+)?)$/.exec(s);       // 12 6 and 12-6: feet and inches
  return m ? +m[1] + (m[2] ? +m[2] / 12 : 0) : NaN;
}
function rescale(k) {
  snapshot();
  const R = (r) => { for (let i = 0; i < 4; i++) r[i] = r3(r[i] * k); };
  for (const f of plan.floors) {
    f.walls.forEach(R); f.openings.forEach((o) => { R(o.rect); if (o.hinge) o.hinge = o.hinge.map((v) => r3(v * k)); });
    f.rooms.forEach((z) => { z.rects.forEach(R); z.area = +(z.area * k * k).toFixed(1); });
    (f.stairs || []).forEach((s) => { R(s.rect); s.words = (s.words || []).map(([t, x, y]) => [t, r3(x * k), r3(y * k)]); });
    (f.labels || []).forEach((l) => { l.at = l.at.map((v) => r3(v * k)); });
    if (f.size) f.size = f.size.map((v) => r3(v * k));
    if (f.bg?.pt_per_ft) f.bg.pt_per_ft = +(f.bg.pt_per_ft / k).toFixed(5);      // the drawing stays where it was under the plan
  }
  if (plan.scale_pt_per_ft) plan.scale_pt_per_ft = +(plan.scale_pt_per_ft / k).toFixed(5);
  plan.scale_source = 'user';
}
// a new wall from a drag: straight across or up, centred on the line of a wall it continues (or flush with the end of
// one it meets), its ends on the far face of a wall they reach so the two overlap and rooms close
function snapWall(ax, ay, bx, by) {
  const f = F(), tol = 10 / view.k, T = (wallIn ?? wallT() * 12) / 12;
  const h = Math.abs(bx - ax) >= Math.abs(by - ay), A = h ? 0 : 2, B = h ? 2 : 0;
  const near = (v, cands) => cands.reduce((best, c) => (Math.abs(c - v) < tol && (best === null || Math.abs(c - v) < Math.abs(best - v)) ? c : best), null);
  const lines = f.walls.flatMap((w) => (horiz(w) === h ? [(w[B] + w[B + 1]) / 2] : [w[B] + T / 2, w[B + 1] - T / 2]));
  const c = near(h ? ay : ax, lines) ?? (h ? ay : ax);
  let lo = Math.min(h ? ax : ay, h ? bx : by), hi = Math.max(h ? ax : ay, h ? bx : by);
  const cross = f.walls.filter((w) => horiz(w) !== h && c >= w[B] - tol && c <= w[B + 1] + tol);
  const at = (p, end) => cross.find((w) => p >= w[A] - tol && p <= w[A + 1] + tol)?.[A + end];
  const faces = f.walls.flatMap((w) => [w[A], w[A + 1]]);
  lo = at(lo, 0) ?? near(lo, faces) ?? lo;
  hi = at(hi, 1) ?? near(hi, faces) ?? hi;
  if (hi - lo < Math.max(T, 0.5)) return null;
  return h ? [r3(lo), r3(hi), r3(c - T / 2), r3(c + T / 2)] : [r3(c - T / 2), r3(c + T / 2), r3(lo), r3(hi)];
}
function stairRect(d, x, y) {
  const r = [Math.min(d.x, x), Math.max(d.x, x), Math.min(d.y, y), Math.max(d.y, y)];
  return r[1] - r[0] >= 1.5 && r[3] - r[2] >= 1.5 ? r.map(r3) : null;
}
// line up the drawing from matched points: page point = origin + (x, -y) * scale, least squares over the pairs
// (one pair moves the drawing, two or more also scale it)
function lineUp() {
  const f = F(), b = bgOf(f);
  const n = pairs.length, P = pairs.map((p) => p[0]), Q = pairs.map((p) => p[1]);
  const mean = (a, i) => a.reduce((s, p) => s + p[i], 0) / n;
  const [u, v, x, y] = [mean(P, 0), mean(P, 1), mean(Q, 0), mean(Q, 1)];
  let s = b.s;
  if (n > 1) {
    let num_ = 0, den = 0;
    for (let i = 0; i < n; i++) { num_ += (P[i][0] - u) * (Q[i][0] - x) - (P[i][1] - v) * (Q[i][1] - y); den += (Q[i][0] - x) ** 2 + (Q[i][1] - y) ** 2; }
    if (den < 1 || !(num_ > 0)) { pairs.pop(); $('hint').textContent = 'Those points are too close together (or crossed): pick two points far apart.'; return draw(); }
    s = num_ / den;
  }
  snapshot();
  setBg(f, { ...b, s, o: [u - x * s, v + y * s], fit: 'matched' });
  $('hint').textContent = n > 1 ? 'Lined up. Check a third corner; Start again to redo.' : 'Moved. Now a second point far from the first: on the drawing, then on the plan.';
  ui();
}

let drag = null;
const PAN = ['select', 'door', 'window', 'scale', 'lineup'];
cv.addEventListener('pointerdown', (e) => {
  if (!plan) return;
  cv.setPointerCapture(e.pointerId);
  const [x, y] = toP(e.offsetX, e.offsetY);
  drag = { X: e.offsetX, Y: e.offsetY, x, y, moved: false };
  const w = tool === 'select' && sel?.kind === 'wall' && F().walls[sel.i];
  if (w && inR(w, x, y, 6 / view.k)) {      // the selected wall: an end lengthens it, the middle moves it across
    const h = horiz(w), a = h ? x : y, A = h ? 0 : 2, m = 10 / view.k;
    drag.grab = { mode: Math.abs(a - w[A]) < m ? 'lo' : Math.abs(a - w[A + 1]) < m ? 'hi' : 'move', w0: [...w],
      ops: F().openings.filter((o) => overlaps(o.rect, w)).map((o) => [o, [...o.rect]]) };
  }
});
cv.addEventListener('pointermove', (e) => {
  if (!drag) return;
  const dx = e.offsetX - drag.X, dy = e.offsetY - drag.Y;
  if (Math.hypot(dx, dy) > 4 && !drag.moved) { drag.moved = true; if (drag.grab) snapshot(); }
  if (!drag.moved) return;
  const [x, y] = toP(e.offsetX, e.offsetY);
  if (drag.grab) {
    const w = F().walls[sel.i], { mode, w0, ops } = drag.grab, h = horiz(w0), A = h ? 0 : 2, B = h ? 2 : 0;
    const d = h ? x - drag.x : y - drag.y, across = h ? y - drag.y : x - drag.x;
    if (mode === 'lo') w[A] = r3(Math.min(w0[A] + d, w0[A + 1] - 0.5));
    else if (mode === 'hi') w[A + 1] = r3(Math.max(w0[A + 1] + d, w0[A] + 0.5));
    else {
      w[B] = r3(w0[B] + across); w[B + 1] = r3(w0[B + 1] + across);
      for (const [o, r] of ops) { o.rect[B] = r3(r[B] + across); o.rect[B + 1] = r3(r[B + 1] + across); }
    }
    return draw();
  }
  if (PAN.includes(tool)) { view.ox += e.movementX; view.oy += e.movementY; draw(); }
  if (tool === 'wall') { drag.preview = snapWall(drag.x, drag.y, x, y); draw(); }
  if (tool === 'stair') { drag.preview = stairRect(drag, x, y); draw(); }
});
cv.addEventListener('pointerup', (e) => {
  const d = drag; drag = null;
  if (!d || !plan) return;
  const f = F(), [x, y] = toP(e.offsetX, e.offsetY);
  if (d.grab) { if (d.moved) { edited(f); ui(); } else { sel = pick(x, y); ui(); } return; }
  if (tool === 'select' && !d.moved) {
    sel = pick(x, y);
    const j = sel ? -1 : plan.floors.findIndex((o, j) => {   // clicked on another plan of the sheet: edit that one
      const off = j !== fi && offsetOf(j), b = off && drawn(o);
      return b && x >= b[0] + off[0] && x <= b[1] + off[0] && y >= b[2] + off[1] && y <= b[3] + off[1];
    });
    if (j >= 0) { const [dx, dy] = offsetOf(j); fi = j; view.ox += dx * view.k; view.oy -= dy * view.k; }
    ui(); draw();
  } else if (tool === 'wall' && d.preview) {
    snapshot(); f.walls.push([...d.preview, 0]); edited(f); ui();
  } else if (tool === 'stair' && d.preview) {
    const r = d.preview, ax = horiz(r) ? 'x' : 'y', run = ax === 'x' ? r[1] - r[0] : r[3] - r[2];
    const start = ax === 'x' ? (Math.abs(d.x - r[0]) < Math.abs(d.x - r[1]) ? r[0] : r[1]) : (Math.abs(d.y - r[2]) < Math.abs(d.y - r[3]) ? r[2] : r[3]);
    const up = ax === 'x' ? ['UP', start, r3((r[2] + r[3]) / 2)] : ['UP', r3((r[0] + r[1]) / 2), start];
    snapshot();
    f.stairs.push({ rect: r, axis: ax, steps: Math.max(3, Math.min(30, Math.round(run * 12 / 10))), up: true, words: [up] });
    edited(f); sel = { kind: 'stair', i: f.stairs.length - 1 }; ui();
  } else if ((tool === 'door' || tool === 'window') && !d.moved) {
    const w = f.walls.find((q) => inR(q, x, y, 6 / view.k));
    if (!w) { $('hint').textContent = 'Click exactly on a wall.'; return; }
    const h = horiz(w), A = h ? 0 : 2, len = w[A + 1] - w[A], wid = Math.min(widths[tool], len);
    const c = Math.max(w[A] + wid / 2, Math.min(w[A + 1] - wid / 2, h ? x : y));
    snapshot();
    f.openings.push({ type: tool, axis: h ? 'x' : 'y',
      rect: h ? [r3(c - wid / 2), r3(c + wid / 2), w[2], w[3]] : [w[0], w[1], r3(c - wid / 2), r3(c + wid / 2)] });
    $('hint').textContent = HINT[tool];
    edited(f); ui();
  } else if (tool === 'scale' && !d.moved) {
    if (scalePts.length === 2) scalePts = [];
    scalePts.push([x, y]); ui();
  } else if (tool === 'lineup' && !d.moved) {
    guessBg(f);
    const b = bgOf(f);
    if (!b) { $('hint').textContent = 'This floor has no page image to line up.'; return; }
    if (!pending) { pending = pagePt(b, x, y); $('hint').textContent = 'Now click the same point on the plan.'; draw(); }
    else { pairs.push([pending, [x, y]]); pending = null; lineUp(); }
  }
});
cv.addEventListener('wheel', (e) => {
  e.preventDefault();
  const z = Math.exp(-e.deltaY * 0.0015);
  view.ox = e.offsetX - (e.offsetX - view.ox) * z;
  view.oy = e.offsetY - (e.offsetY - view.oy) * z;
  view.k *= z;
  draw();
}, { passive: false });
addEventListener('resize', draw);
$('nclose').onclick = () => { $('notice').hidden = true; };

$('save').onclick = async () => {        // a traced plan is long work: keep it without building
  plan.furnish = $('furn').checked;
  const r = await fetch(`../api/jobs/${job}/plan`, { method: 'POST', body: JSON.stringify(plan) });
  $('saved').textContent = r.ok ? 'Saved' : (await r.json()).error;
  $('saved').className = r.ok ? 'muted' : 'err';
  setTimeout(() => { $('saved').textContent = ''; }, 2500);
};
$('build').onclick = async () => {
  const why = checkBuildable();
  if (why) { $('why').classList.remove('flash'); void $('why').offsetWidth; $('why').classList.add('flash'); return; }
  $('build').disabled = true;
  plan.furnish = $('furn').checked;
  let r = await fetch(`../api/jobs/${job}/plan`, { method: 'POST', body: JSON.stringify(plan) });
  if (r.ok) r = await fetch(`../api/jobs/${job}/build`, { method: 'POST', body: JSON.stringify({ quality: $('quality').value}) });
  const j = await r.json();
  if (!r.ok) { alert(j.error); $('build').disabled = false; return; }
  buildStatus({ stage: 'queued', progress: 0, message: 'Queued' });
};
poll();
if (EMBED) addEventListener('message', async (e) => {         // only the page that frames this one is listened to
  if (e.source !== parent || !e.data || e.data.source !== 'planto3d-host' || e.data.type !== 'save') return;
  if (!plan) return tell({ type: 'saved', ok: false, error: 'The plan is not loaded yet.' });
  plan.furnish = e.data.furnish !== false;
  $('furn').checked = plan.furnish;
  const why = problem();          // saved either way (a traced plan is kept half done); the host builds only when buildable
  try {
    const r = await fetch(`../api/jobs/${job}/plan`, { method: 'POST', body: JSON.stringify(plan) });
    tell({ type: 'saved', ok: r.ok, error: r.ok ? null : (await r.json()).error, buildable: !why, problem: why });
  } catch { tell({ type: 'saved', ok: false, error: 'The plan could not be saved.', buildable: !why, problem: why }); }
});
$('models').onclick = () => {           // the furniture page, inside this one: replace a model, then build
  $('modelsframe').src = 'furniture.html?embed';
  $('modelsdlg').showModal();
};
// for tests and tools driving the page from outside
window.__review = { get plan() { return plan; }, get floor() { return fi; }, problem, parseLength, setTool, toC,
  fromPage: (u, v) => planPt(bgOf(F()), u, v) };
