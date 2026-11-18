// The review page with plans that do not come from the detector, in a real (headless) browser against a running
// server. No build: about 30 s.
//  1. upload without the detector (X-Detect: 0), import an empty plan (reader "trace") and trace it inside an
//     iframe (?embed): walls by dragging, the scale from two points and a typed distance, a door, a window, stairs;
//     rooms follow the walls; the host hears ready / buildable / saved and the saved plan has it all;
//  2. import a plan read elsewhere (reader "ai") with a notice: the page says so, the drawing is not lined up until
//     two points are matched, and a metric distance rescales it;
//  3. the import API refuses bad plans (400) and imports while the detector runs (409).
// CHROME=/path/to/chromium node tests/test_review.mjs examples/sample_plan.pdf [http://127.0.0.1:8080]
// TRACE=trace.json traces another drawing (see SAMPLE below for its fields); SHOTS=dir saves screenshots;
// MODE=standalone traces without the iframe; KEEP=1 keeps the jobs.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert';
const [pdf, base = 'http://127.0.0.1:8080'] = process.argv.slice(2);
const sleep = (t) => new Promise((r) => setTimeout(r, t));
const CH = process.env.CHROME || 'chromium';
const ANGLE = process.env.ANGLE || (process.platform === 'darwin' ? 'metal' : 'gl-egl');
const SHOTS = process.env.SHOTS, EMBED = process.env.MODE !== 'standalone';
// what to trace, in points of the (turned) page from its top-left corner: the sample plan's outer walls, one inner
// wall, the outer width for the scale, a door, a window and a stair flight drawn from its bottom step
const SAMPLE = { turn: 0, walls: [[209.5, 440.5, 632.5, 440.5], [209.5, 113.5, 632.5, 113.5], [209.5, 440.5, 209.5, 113.5],
  [632.5, 440.5, 632.5, 113.5], [209.5, 265, 632.5, 265]], scale: [[209.5, 440.5], [632.5, 440.5], `35'3"`], feet: 35.25,
  door: [334, 440.5], window: [500, 113.5], stair: [[560, 330], [620, 300]] };
const T = process.env.TRACE ? JSON.parse(fs.readFileSync(process.env.TRACE, 'utf8')) : SAMPLE;
if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });
const api = async (p, opts = {}) => {
  const r = await fetch(base + p, { ...opts, body: opts.body && typeof opts.body !== 'string' && !(opts.body instanceof Buffer) ? JSON.stringify(opts.body) : opts.body });
  return [r.status, await r.json()];
};
const upload = async (detect) => (await api('/api/upload', { method: 'POST', body: fs.readFileSync(pdf),
  headers: { 'X-Filename': encodeURIComponent(path.basename(pdf)), ...(detect ? {} : { 'X-Detect': '0' }) } }))[1].id;
const port = 9400 + Math.floor(Math.random() * 400);
const prof = fs.mkdtempSync(path.join(process.env.TMPDIR || '/tmp', 'planto3d-chrome-'));
const ch = spawn(CH, ['--headless=new', '--no-sandbox', `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, `--use-angle=${ANGLE}`,
  '--ignore-gpu-blocklist', '--window-size=1400,900', '--hide-scrollbars', 'about:blank'], { stdio: 'ignore' });
const jobs = [];
try {
  let targets;
  for (let i = 0; i < 100 && !targets; i++) { try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); } catch { await sleep(200); } }
  const ws = new WebSocket(targets.find((t) => t.type === 'page').webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener('open', r));
  let id = 0; const pend = new Map(), errors = [];
  ws.addEventListener('message', (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
    if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
  });
  const cdp = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  await cdp('Runtime.enable');
  await cdp('Emulation.setDeviceMetricsOverride', { width: 1400, height: 900, deviceScaleFactor: 1, mobile: false });
  const ev = async (expr) => {
    const r = (await cdp('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result;
    if (r?.exceptionDetails) throw new Error(`${expr.slice(0, 80)}: ${r.exceptionDetails.exception?.description || r.exceptionDetails.text}`);
    return r?.result?.value;
  };
  const until = async (what, expr, ms = 20000) => {
    for (const end = Date.now() + ms; ; await sleep(150)) {
      const v = await ev(expr);
      if (v) return v;
      if (Date.now() > end) throw new Error(`timed out: ${what}`);
    }
  };
  const shot = async (name) => {
    if (!SHOTS) return;
    const r = await cdp('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(SHOTS, name + '.png'), Buffer.from(r.result.data, 'base64'));
  };
  // the review page: this window, or the iframe of a host page on the same server (its scripts can then be reached)
  let W = 'window';
  const $ = (q) => `${W}.document.querySelector(${JSON.stringify(q)})`;
  const open = async (job, embed) => {
    if (embed) {           // a host page, as our product's: it frames the review page and listens to it
      await cdp('Page.navigate', { url: `${base}/api/nothing` });
      await sleep(400);
      await ev(`document.open(); document.write('<body style="margin:0"><iframe id="f" style="position:absolute;left:20px;top:30px;width:1340px;height:840px;border:0" src="${base}/web/edit.html?job=${job}&embed"></iframe></body>'); document.close();
        window.msgs = []; addEventListener('message', (e) => { if (e.data?.source === 'planto3d') msgs.push(e.data); }); true`);
      W = 'frames[0]';
    } else {
      await cdp('Page.navigate', { url: `${base}/web/edit.html?job=${job}` });
      W = 'window';
    }
    await until('the review page loads its plan', `!!(${W}.__review?.plan) && getComputedStyle(${$('#wait')}).display === 'none'`);
    await sleep(500);
  };
  // page points -> screen pixels of the canvas, through the page's own view
  const at = async (u, v) => ev(`(() => { const R = ${W}.__review, c = ${$('#cv')}.getBoundingClientRect();
    const f = ${W === 'window' ? '{x:0,y:0}' : 'document.getElementById("f").getBoundingClientRect()'};
    const [X, Y] = R.toC(...R.fromPage(${u}, ${v})); return [f.x + c.x + X, f.y + c.y + Y]; })()`);
  const mouse = (type, [x, y]) => cdp('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons: type === 'mouseReleased' ? 0 : 1, clickCount: 1 });
  const click = async (p) => { await mouse('mousePressed', p); await mouse('mouseReleased', p); await sleep(60); };
  const dragAt = async (a, b) => {
    await mouse('mousePressed', a);
    for (let k = 1; k <= 8; k++) await mouse('mouseMoved', [a[0] + (b[0] - a[0]) * k / 8, a[1] + (b[1] - a[1]) * k / 8]);
    await mouse('mouseReleased', b); await sleep(60);
  };
  const tool = (t) => ev(`${$(`#tools button[data-t="${t}"]`)}.click()`);
  const plan = () => ev(`JSON.parse(JSON.stringify(${W}.__review.plan))`);

  // ---- 1. trace from nothing
  let job = await upload(false); jobs.push(job);
  let st = (await api(`/api/jobs/${job}`))[1];
  assert.equal(st.stage, 'uploaded', 'X-Detect: 0 leaves the job at "uploaded"');
  assert(st.pages?.length >= 1 && (await fetch(`${base}/jobs/${job}/page-1.png`)).ok, 'the page images are drawn on upload');
  let [code, res] = await api(`/api/jobs/${job}/import`, { method: 'POST', body: { plan: null, reader: 'trace', notice: 'Nothing could be read from this drawing.' } });
  assert.equal(code, 200, JSON.stringify(res));
  st = (await api(`/api/jobs/${job}`))[1];
  assert.deepEqual([st.stage, st.reader, st.notice, st.floors], ['detected', 'trace', 'Nothing could be read from this drawing.', ['Ground Floor']]);
  await open(job, EMBED);
  if (EMBED) {
    const ready = await until('ready message', `msgs.find((m) => m.type === 'ready')`);
    assert.deepEqual([ready.reader, ready.notice, ready.buildable], ['trace', 'Nothing could be read from this drawing.', false], JSON.stringify(ready));
    assert.match(ready.problem, /no walls/);
    assert.equal(await ev(`getComputedStyle(${$('#notice')}).display`), 'none', 'in embed mode the host shows the notice');
  } else {
    assert.match(await ev(`${$('#ntext')}.textContent`), /could not be read automatically/);
    assert.equal(await ev(`${$('#nmore')}.textContent`), 'Nothing could be read from this drawing.');
  }
  // the page image is drawn: plenty of dark pixels on the canvas before anything is traced
  const ink = `(() => { const c = ${$('#cv')}, d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0;
    for (let i = 0; i < d.length; i += 4) if (d[i + 3] && d[i] + d[i + 1] + d[i + 2] < 600) n++; return n; })()`;
  assert(await ev(ink) > 2000, 'the PDF page should show behind an empty plan');
  await ev(`${$('#showbg')}.click()`);
  assert(await ev(ink) < 50, 'the toggle hides the page');
  await ev(`${$('#showbg')}.click()`);
  await shot('trace-1-opens-on-the-page');
  if (T.turn) {
    await ev(`${$(T.turn > 0 ? '#turnr' : '#turnl')}.click()`);
    assert.equal((await plan()).floors[0].bg.rot, (T.turn + 360) % 360);
    await shot('trace-2-page-turned');
  }
  await tool('wall');
  for (const [u0, v0, u1, v1] of T.walls) await dragAt(await at(u0, v0), await at(u1, v1));
  let p = await plan();
  assert.equal(p.floors[0].walls.length, T.walls.length, 'one wall per drag');
  assert(p.floors[0].rooms.length >= 2, `rooms follow the walls (got ${p.floors[0].rooms.length})`);
  assert.match(await ev(`${W}.__review.problem()`), /scale/, 'a traced plan needs its scale before it is built');
  await shot('trace-3-walls-and-rooms');
  await tool('scale');
  await click(await at(...T.scale[0]));
  await click(await at(...T.scale[1]));
  await until('distance box', `!!${$('#sdist')}`);
  await shot('trace-4-scale-asks-distance');
  await ev(`${$('#sdist')}.value = ${JSON.stringify(T.scale[2])}; ${$('#sset')}.click()`);
  p = await plan();
  assert.equal(p.scale_source, 'user');
  const w0 = p.floors[0].walls[0];
  // (the first wall met no other wall: it runs from point to point; later ones may reach a far face)
  const len = w0[1] - w0[0], t = w0[3] - w0[2];
  assert(Math.abs(len - T.feet) < 0.15 || Math.abs(len - T.feet - t) < 0.15, `the traced width is the typed distance (${len})`);
  await tool('door'); await click(await at(...T.door));
  await tool('window'); await click(await at(...T.window));
  if (T.stair) { await tool('stair'); await dragAt(await at(...T.stair[0]), await at(...T.stair[1])); }
  p = await plan();
  const f = p.floors[0];
  assert.deepEqual(f.openings.map((o) => o.type), ['door', 'window'], 'a door and a window on the walls');
  if (T.stair) assert.equal(f.stairs.length, 1, 'a stair flight');
  assert.equal(await ev(`${W}.__review.problem()`), null, 'the traced plan is buildable');
  await tool('select');
  await shot('trace-5-door-window-stairs');
  if (EMBED) {
    const b = await until('buildable message', `msgs.find((m) => m.type === 'buildable' && m.buildable)`);
    assert.equal(b.problem, null);
    await ev(`frames[0].postMessage({ source: 'planto3d-host', type: 'save', furnish: true }, '*')`);
    const saved = await until('saved message', `msgs.find((m) => m.type === 'saved')`);
    assert.deepEqual([saved.ok, saved.buildable], [true, true], JSON.stringify(saved));
  } else {
    await ev(`${$('#save')}.click()`);
    await until('saved', `${$('#saved')}.textContent === 'Saved'`);
  }
  const disk = (await api(`/jobs/${job}/plan.json`))[1];
  assert.deepEqual(disk.floors[0].walls, f.walls, 'the saved plan is the traced one');
  // where the plan lies on its page: its own bg, or (an empty plan made by the server) origin_pt at the plan's scale
  const bg = disk.floors[0].bg?.pt_per_ft ? disk.floors[0].bg : { pt_per_ft: disk.scale_pt_per_ft, origin_pt: disk.floors[0].origin_pt };
  assert(disk.floors[0].rooms.length >= 2 && bg.pt_per_ft > 0 && bg.origin_pt, 'rooms and the page fit are saved');
  console.log(`traced ${path.basename(pdf)}: job ${job}, ${f.walls.length} walls, ${f.rooms.length} rooms, ${f.openings.length} openings, ${f.stairs.length} stairs`);
  if (!process.env.TRACE) {           // (another drawing: only the tracing)
  // ---- 2. a plan read elsewhere, not lined up with its page
  job = await upload(false); jobs.push(job);
  const ai = JSON.parse(JSON.stringify(disk));
  ai.scale_source = 'given';
  for (const fl of ai.floors) { delete fl.bg; delete fl.origin_pt; fl.walls = fl.walls.map((w) => [w[0] + 100, w[1] + 100, w[2] + 50, w[3] + 50, w[4]]); fl.rooms = []; fl.openings = []; fl.stairs = []; delete fl.auto_rooms; }
  [code, res] = await api(`/api/jobs/${job}/import`, { method: 'POST', body: { plan: ai, reader: 'ai', notice: 'The scale was read from the dimension labels.' } });
  assert.equal(code, 200, JSON.stringify(res));
  W = 'window';
  await open(job, false);
  assert.match(await ev(`${$('#ntext')}.textContent`), /AI plan reader: check the walls, doors and sizes/);
  assert.equal(await ev(`${$('#nmore')}.textContent`), 'The scale was read from the dimension labels.');
  assert.match(await ev(`${$('#bgstate')}.textContent`), /Not lined up/);
  assert((await plan()).floors[0].rooms.length >= 2, 'rooms are found for a plan that came without them');
  await shot('ai-1-not-lined-up');
  // line up: the traced plan's first wall ends are known points of the drawing
  const W0 = disk.floors[0].walls;
  const page = (x, y) => [bg.origin_pt[0] + x * bg.pt_per_ft, bg.origin_pt[1] - y * bg.pt_per_ft];
  const planC = (x, y) => ev(`(() => { const R = window.__review, c = ${$('#cv')}.getBoundingClientRect(), [X, Y] = R.toC(${x}, ${y}); return [c.x + X, c.y + Y]; })()`);
  await tool('lineup');
  for (const [x, y] of [[W0[0][0], W0[0][2]], [W0[1][1], W0[1][3]]]) {
    await click(await at(...page(x, y)));
    await click(await planC(x + 100, y + 50));
  }
  p = await plan();
  assert.equal(p.floors[0].bg.fit, 'matched');
  const [u, v] = [p.floors[0].bg.origin_pt[0] + (W0[0][0] + 100) * p.floors[0].bg.pt_per_ft, p.floors[0].bg.origin_pt[1] - (W0[0][2] + 50) * p.floors[0].bg.pt_per_ft];
  const [u0, v0] = page(W0[0][0], W0[0][2]);
  assert(Math.hypot(u - u0, v - v0) < 4, `two matched points line the drawing up (${(u - u0).toFixed(1)}, ${(v - v0).toFixed(1)} pt off)`);
  assert.match(await ev(`${$('#bgstate')}.textContent`), /Lined up by hand/);
  await shot('ai-2-lined-up');
  const lens = await ev(`["12'6\\"", "12' 6", "12'-6\\"", '12.5 ft', '150"', '3.8 m', '3,8 m', '380 cm', '3800mm', '12', 'abc', ''].map((s) => +window.__review.parseLength(s).toFixed(3))`);
  assert.deepEqual(lens, [12.5, 12.5, 12.5, 12.5, 12.5, 12.467, 12.467, 12.467, 12.467, 12, null, null], `typed distances: ${lens}`);
  const before = (await plan()).floors[0].walls[0];
  await tool('scale');
  await click(await planC(before[0], before[2]));
  await click(await planC(before[1], before[2]));
  await until('distance box', `!!${$('#sdist')}`);
  await ev(`${$('#sdist')}.value = '3.8 m'; ${$('#sset')}.click()`);
  const after = (await plan()).floors[0].walls[0];
  assert(Math.abs(after[1] - after[0] - 3.8 / 0.3048) < 0.05, `3.8 m is ${3.8 / 0.3048} ft (${after[1] - after[0]})`);
  await shot('ai-3-rescaled-in-metres');

  // ---- 3. the import API
  const bad = async (body, re) => { const [c, j] = await api(`/api/jobs/${job}/import`, { method: 'POST', body }); assert.equal(c, 400, JSON.stringify(j)); assert.match(j.error, re); };
  await bad({ plan: null, reader: 'robot' }, /reader/);
  await bad({ plan: { floors: [] }, reader: 'ai' }, /floors/);
  await bad({ plan: { floors: [{ walls: [[0, 'x', 0, 1]] }] }, reader: 'ai' }, /number/);
  await bad({ plan: { floors: [{ walls: [[5, 1, 0, 1]] }] }, reader: 'ai' }, /x0 < x1/);
  await bad({ plan: { floors: [{ walls: [], items: [] }] }, reader: 'ai' }, /furniture/);
  await bad({ plan: { floors: [{ walls: [], rooms: [{ type: 'spa', rects: [[0, 1, 0, 1]] }] }] }, reader: 'ai' }, /type/);
  await bad({ plan: null, reader: 'ai', notice: 'x'.repeat(301) }, /300/);
  const detecting = await upload(true); jobs.push(detecting);
  [code, res] = await api(`/api/jobs/${detecting}/import`, { method: 'POST', body: { plan: null, reader: 'manual' } });
  assert.equal(code, 409, 'no import while the detector reads the drawing');
  st = (await api(`/api/jobs/${detecting}`))[1];
  for (let i = 0; i < 100 && ['uploaded', 'detecting'].includes(st.stage); i++) { await sleep(300); st = (await api(`/api/jobs/${detecting}`))[1]; }
  assert.deepEqual([st.reader, st.notice], ['detector', ''], 'a detected plan says so');
  assert.deepEqual(errors, [], 'no script errors');
  console.log('PASS upload without detection, import (empty, ai, refused), tracing in embed mode, scale, line up, notices');
  }
} finally {
  await new Promise((r) => { ch.once('exit', r); ch.kill(); setTimeout(r, 5000); });
  try { fs.rmSync(prof, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch { /* the browser's last writes */ }
  if (!process.env.KEEP) for (const j of jobs) await fetch(`${base}/api/jobs/${j}`, { method: 'DELETE' }).catch(() => {});
}
process.exit(0);
