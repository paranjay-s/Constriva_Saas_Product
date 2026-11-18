// Review screen: the detected plan drawn over the PDF page; fix walls / openings / room types, then build.
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
let plan, fi = 0, sel = null, tool = 'select', img = {}, history = [];
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
  if (!plan) { await load(); tell({ type: 'ready', floors: plan.floors.length }); }
  buildStatus(st);
}
async function load() {
  plan = await fetch(`../jobs/${job}/plan.json`).then((r) => r.json());
  $('wait').style.display = 'none';
  plan.floors.forEach((f, i) => {
    const b = document.createElement('button');
    b.textContent = f.name;
    b.onclick = () => { fi = i; sel = null; fit(); ui(); };
    $('tabs').appendChild(b);
  });
  for (const p of new Set(plan.floors.map((f) => f.page || 1))) {
    const im = new Image();
    im.src = `../jobs/${job}/page-${p}.png`;
    im.onload = draw;
    img[p] = im;
  }
  $('fh').value = plan.floor_height;
  $('furn').checked = plan.furnish !== false;
  fit(); ui();
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
function fit() {
  const f = F(), [w, h] = f.size, W = cv.clientWidth, H = cv.clientHeight;
  view.k = Math.min((W - 60) / w, (H - 60) / h);
  view.ox = (W - w * view.k) / 2;
  view.oy = (H + h * view.k) / 2;
  draw();
}
function wallT() {
  const t = F().walls.map((w) => Math.min(w[1] - w[0], w[3] - w[2])).sort((a, b) => a - b);
  return t[Math.floor(t.length / 2)] || 0.375;
}
function snapshot() { history.push(JSON.stringify(plan)); if (history.length > 50) history.shift(); }

// ---------------------------------------------------------------- drawing
function rectC(r) { const [a, b] = toC(r[0], r[3]), [c, d] = toC(r[1], r[2]); return [a, b, c - a, d - b]; }
// floor j's plan coordinates -> the current floor's (both are measured from their own lower-left corner)
function offsetOf(j) {
  const s = plan.scale_pt_per_ft, a = F().origin_pt, b = plan.floors[j].origin_pt;
  return [(b[0] - a[0]) / s, (a[1] - b[1]) / s];
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
  for (const st of f.stairs || []) { g.fillStyle = 'rgba(138,90,43,.55)'; g.fillRect(...rectC(mv(st.rect))); }
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
    const r = mv(z.rects.reduce((a, b) => ((b[1] - b[0]) * (b[3] - b[2]) > (a[1] - a[0]) * (a[3] - a[2]) ? b : a)));
    if ((r[1] - r[0]) * view.k < 30) return;
    const [x, y] = toC((r[0] + r[1]) / 2, (r[2] + r[3]) / 2);
    g.fillStyle = '#111';
    g.fillText(z.type, x, y);
  });
  g.globalAlpha = 1;
}
function draw() {
  if (!plan) return;
  const dpr = devicePixelRatio || 1;
  cv.width = cv.clientWidth * dpr; cv.height = cv.clientHeight * dpr;
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, cv.clientWidth, cv.clientHeight);
  const f = F(), s = plan.scale_pt_per_ft, im = img[f.page || 1];
  if (im?.complete) {
    const sc = view.k / (s * D);
    g.globalAlpha = 0.45;
    g.drawImage(im, view.ox - f.origin_pt[0] * view.k / s, view.oy - f.origin_pt[1] * view.k / s, im.width * sc, im.height * sc);
    g.globalAlpha = 1;
  }
  // the other plans on this sheet stay visible (faded); click one to edit it
  plan.floors.forEach((o, j) => { if (j !== fi && (o.page || 1) === (f.page || 1)) drawFloor(o, ...offsetOf(j), false); });
  drawFloor(f, 0, 0, true);
  if (drag?.preview) { g.strokeStyle = '#000'; g.setLineDash([4, 3]); g.strokeRect(...rectC(drag.preview)); g.setLineDash([]); }
  for (const p of scalePts) { const [x, y] = toC(...p); g.fillStyle = '#b0562b'; g.beginPath(); g.arc(x, y, 5, 0, 7); g.fill(); }
}

// ---------------------------------------------------------------- side panel
function ui() {
  document.querySelectorAll('#tabs button').forEach((b, i) => b.classList.toggle('on', i === fi));
  const f = F();
  $('fname').value = f.name;
  $('scale').textContent = `${plan.floors.length} floor${plan.floors.length > 1 ? 's' : ''} · scale ${plan.scale_source === 'labels'
    ? 'read from room sizes' : 'GUESSED - use Set scale'}`;
  const P = $('props');
  P.innerHTML = '';
  if (!sel) { P.innerHTML = `<h3>Selection</h3><p class="muted" style="font-size:13px">${f.walls.length} walls, ${f.openings.length} openings, ${f.rooms.length} rooms</p>`; draw(); return; }
  const h = document.createElement('div');
  const del = () => { snapshot(); f[{ wall: 'walls', opening: 'openings', stair: 'stairs' }[sel.kind]].splice(sel.i, 1); sel = null; ui(); };
  if (sel.kind === 'wall') {
    const w = f.walls[sel.i];
    h.innerHTML = `<h3>Wall</h3><div class="row"><span>${(Math.max(w[1] - w[0], w[3] - w[2])).toFixed(1)} ft long</span>
      <select id="wl"><option value="0">Full height</option><option value="1">Low / parapet</option></select></div>`;
    P.appendChild(h);
    $('wl').value = w[4]; $('wl').onchange = (e) => { snapshot(); w[4] = +e.target.value; draw(); };
  } else if (sel.kind === 'opening') {
    const o = f.openings[sel.i];
    h.innerHTML = `<h3>Opening</h3><div class="row"><span>${(Math.max(o.rect[1] - o.rect[0], o.rect[3] - o.rect[2])).toFixed(1)} ft wide</span>
      <select id="ot"><option>door</option><option>window</option><option>opening</option></select></div>`;
    P.appendChild(h);
    $('ot').value = o.type; $('ot').onchange = (e) => { snapshot(); o.type = e.target.value; draw(); };
  } else if (sel.kind === 'room') {
    const z = f.rooms[sel.i];
    h.innerHTML = `<h3>Room</h3><div class="row"><span>Type</span><select id="rt">${TYPES.map((t) => `<option>${t}</option>`).join('')}</select></div>
      <div class="row" style="margin-top:6px"><span>Label</span><input type="text" id="rl" style="width:160px"></div>
      <p class="muted" style="font-size:12px">${+z.area} sq ft. Furniture follows the type.</p>`;
    P.appendChild(h);
    $('rt').value = z.type; $('rt').onchange = (e) => { snapshot(); z.type = e.target.value; draw(); };
    $('rl').value = z.label || ''; $('rl').oninput = (e) => { z.label = e.target.value; };
  } else if (sel.kind === 'stair') {
    h.innerHTML = '<h3>Stair flight</h3>';
    P.appendChild(h);
  }
  if (sel.kind !== 'room') {
    const b = document.createElement('button');
    b.className = 'btn ghost'; b.textContent = 'Delete'; b.style.marginTop = '8px'; b.onclick = del;
    P.appendChild(b);
  }
  draw();
}
$('fname').oninput = (e) => { F().name = e.target.value; document.querySelectorAll('#tabs button')[fi].textContent = e.target.value; };
$('fh').onchange = (e) => { plan.floor_height = Math.max(8, Math.min(14, +e.target.value || 10)); };

// ---------------------------------------------------------------- tools
const HINT = {
  select: 'Click a wall, opening or room to edit it, or another floor plan to switch to it. Drag to pan, scroll to zoom.',
  wall: 'Drag along the line of the new wall.',
  door: 'Click on a wall where the door should be (3 ft wide).',
  window: 'Click on a wall where the window should be (4 ft wide).',
  scale: 'Click two points a known distance apart, then type that distance.',
};
let scalePts = [];
document.querySelectorAll('#tools button[data-t]').forEach((b) => b.onclick = () => {
  tool = b.dataset.t; scalePts = [];
  document.querySelectorAll('#tools button[data-t]').forEach((x) => x.classList.toggle('on', x === b));
  $('hint').textContent = HINT[tool];
  draw();
});
$('undo').onclick = () => { if (history.length) { plan = JSON.parse(history.pop()); sel = null; ui(); } };
addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT') return;
  if ((e.key === 'Delete' || e.key === 'Backspace') && sel && sel.kind !== 'room') {
    snapshot(); F()[{ wall: 'walls', opening: 'openings', stair: 'stairs' }[sel.kind]].splice(sel.i, 1); sel = null; ui();
  }
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
function parseFeet(s) {
  const m = /^\s*(\d+(?:\.\d+)?)\s*'?\s*(?:-?\s*(\d+(?:\.\d+)?)\s*"?)?\s*$/.exec(s || '');
  return m ? +m[1] + (m[2] ? +m[2] / 12 : 0) : NaN;
}
function rescale(k) {
  snapshot();
  const R = (r) => { for (let i = 0; i < 4; i++) r[i] *= k; };
  for (const f of plan.floors) {
    f.walls.forEach(R); f.openings.forEach((o) => { R(o.rect); if (o.hinge) o.hinge = o.hinge.map((v) => v * k); });
    f.rooms.forEach((z) => { z.rects.forEach(R); z.area = +(z.area * k * k).toFixed(1); });
    (f.stairs || []).forEach((s) => { R(s.rect); s.words = s.words.map(([t, x, y]) => [t, x * k, y * k]); });
    (f.labels || []).forEach((l) => { l.at = l.at.map((v) => v * k); });
    f.size = f.size.map((v) => v * k);
  }
  plan.scale_pt_per_ft /= k;
  plan.scale_source = 'user';
}

let drag = null;
cv.addEventListener('pointerdown', (e) => {
  cv.setPointerCapture(e.pointerId);
  const [x, y] = toP(e.offsetX, e.offsetY);
  drag = { X: e.offsetX, Y: e.offsetY, x, y, moved: false };
});
cv.addEventListener('pointermove', (e) => {
  if (!drag) return;
  const dx = e.offsetX - drag.X, dy = e.offsetY - drag.Y;
  if (Math.hypot(dx, dy) > 4) drag.moved = true;
  if (tool === 'select' && drag.moved) { view.ox += e.movementX; view.oy += e.movementY; draw(); }
  if (tool === 'wall' && drag.moved) {
    const [x, y] = toP(e.offsetX, e.offsetY), t = wallT() / 2;
    drag.preview = Math.abs(x - drag.x) > Math.abs(y - drag.y)
      ? [Math.min(x, drag.x), Math.max(x, drag.x), drag.y - t, drag.y + t]
      : [drag.x - t, drag.x + t, Math.min(y, drag.y), Math.max(y, drag.y)];
    draw();
  }
});
cv.addEventListener('pointerup', (e) => {
  const d = drag; drag = null;
  if (!d) return;
  const f = F(), [x, y] = toP(e.offsetX, e.offsetY);
  if (tool === 'select' && !d.moved) {
    sel = pick(x, y);
    const j = sel ? -1 : plan.floors.findIndex((o, j) => {   // clicked on another plan of the sheet: edit that one
      if (j === fi || (o.page || 1) !== (f.page || 1)) return false;
      const [dx, dy] = offsetOf(j);
      return x >= dx && x <= dx + o.size[0] && y >= dy && y <= dy + o.size[1];
    });
    if (j >= 0) { const [dx, dy] = offsetOf(j); fi = j; view.ox += dx * view.k; view.oy -= dy * view.k; }
    ui(); draw();
  }
  else if (tool === 'wall' && d.preview) { snapshot(); f.walls.push([...d.preview.map((v) => +v.toFixed(3)), 0]); draw(); }
  else if ((tool === 'door' || tool === 'window') && !d.moved) {
    const w = f.walls.find((q) => inR(q, x, y, 6 / view.k));
    if (!w) { $('hint').textContent = 'Click exactly on a wall.'; return; }
    const half = tool === 'door' ? 1.5 : 2, horiz = w[1] - w[0] >= w[3] - w[2];
    snapshot();
    f.openings.push({ type: tool, axis: horiz ? 'x' : 'y',
      rect: horiz ? [x - half, x + half, w[2], w[3]] : [w[0], w[1], y - half, y + half] });
    draw();
  } else if (tool === 'scale' && !d.moved) {
    scalePts.push([x, y]); draw();
    if (scalePts.length === 2) {
      const meas = Math.hypot(scalePts[1][0] - scalePts[0][0], scalePts[1][1] - scalePts[0][1]);
      const real = parseFeet(prompt(`Measured ${meas.toFixed(2)} ft on the drawing. Real distance (e.g. 12'6")?`, meas.toFixed(1)));
      scalePts = [];
      if (real > 0 && meas > 0) { rescale(real / meas); fit(); ui(); } else draw();
    }
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

$('build').onclick = async () => {
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
  try {
    const r = await fetch(`../api/jobs/${job}/plan`, { method: 'POST', body: JSON.stringify(plan) });
    tell({ type: 'saved', ok: r.ok, error: r.ok ? null : (await r.json()).error });
  } catch { tell({ type: 'saved', ok: false, error: 'The plan could not be saved.' }); }
});
$('models').onclick = () => {           // the furniture page, inside this one: replace a model, then build
  $('modelsframe').src = 'furniture.html?embed';
  $('modelsdlg').showModal();
};
