// End-to-end check of the site in a real (headless) browser, against a running server:
// the upload page rejects a non-PDF and accepts a PDF; the review page's "Furniture" box, unticked, gives a draft build
// whose saved plan has furnish=false, and the build box shows status words and the time left; in the walkthrough, P saves a 4K-size PNG, R records a video, M enlarges the map and T-T returns to walking.
// Takes about 2 min (one draft build); removes its own job.
// CHROME=/path/to/chromium node tests/test_site.mjs <plan.pdf> [http://127.0.0.1:8080]
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert';
import { fileURLToPath } from 'node:url';
import { entrance } from '../web/walk.js';
const [pdf, base = 'http://127.0.0.1:8080'] = process.argv.slice(2);
const sleep = (t) => new Promise((r) => setTimeout(r, t));
const CH = process.env.CHROME || 'chromium';
// WebGL backend of the headless browser: EGL on Linux, Metal on a Mac (set ANGLE to choose another)
const ANGLE = process.env.ANGLE || (process.platform === 'darwin' ? 'metal' : 'gl-egl');
const port = 9400 + Math.floor(Math.random() * 400);
const ch = spawn(CH, ['--headless=new', '--no-sandbox', `--remote-debugging-port=${port}`, `--use-angle=${ANGLE}`, '--ignore-gpu-blocklist', '--enable-gpu', 'about:blank'], { stdio: 'ignore' });
let job;
try {
  let targets;
  for (let i = 0; i < 100 && !targets; i++) { try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); } catch { await sleep(200); } }
  const ws = new WebSocket(targets.find((t) => t.type === 'page').webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener('open', r));
  let id = 0; const pend = new Map();
  ws.addEventListener('message', (e) => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } });
  const cdp = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const ev = async (expr) => (await cdp('Runtime.evaluate', { expression: expr, returnByValue: true })).result?.result?.value;
  const choose = async (file) => {
    const { result } = await cdp('Runtime.evaluate', { expression: `document.getElementById('file')` });
    await cdp('DOM.setFileInputFiles', { files: [file], objectId: result.result.objectId });
  };
  await cdp('Page.navigate', { url: base + '/' });
  await sleep(1000);
  await choose(fileURLToPath(import.meta.url));                  // this script: not a PDF (a URL's pathname keeps %20 for a space)
  for (let i = 0; i < 50 && !(await ev(`document.getElementById('msg').className`)); i++) await sleep(100);
  assert.match(await ev(`document.getElementById('msg').textContent`), /PDF/, 'a non-PDF should be refused with a message');
  assert.equal(await ev(`document.getElementById('drop').classList.contains('busy')`), false, 'upload box should be usable again');
  await choose(path.resolve(pdf));
  for (let i = 0; i < 100 && !job; i++) { await sleep(200); job = /edit\.html\?job=([a-f0-9]{12})/.exec(await ev('location.href') || '')?.[1]; }
  assert(job, 'a PDF should open the review page');
  for (let i = 0; i < 150 && (await ev(`getComputedStyle(document.getElementById('wait')).display`)) !== 'none'; i++) await sleep(200);
  assert.equal(await ev(`document.getElementById('furn').checked`), true, 'Furniture box should start ticked');
  await ev(`document.getElementById('furn').click(); document.getElementById('quality').value = 'draft'; document.getElementById('build').click()`);
  let st, sawEta = false, sawWord = false, sawStep = false;
  for (let i = 0; i < 400; i++) {
    st = await (await fetch(`${base}/api/jobs/${job}`)).json();
    if (['done', 'failed'].includes(st.stage)) break;
    sawEta ||= /left|almost done/.test(await ev(`document.getElementById('beta').textContent`));
    sawStep ||= /baking light|exporting model|building walls/.test(await ev(`document.getElementById('bmsg').textContent`));
    sawWord ||= /^\S.+…$/.test(await ev(`document.getElementById('bfun').hidden ? '' : document.getElementById('bword').textContent`));
    await sleep(1500);
  }
  assert.equal(st.stage, 'done', `build ${st.stage}: ${st.message}`);
  assert(sawEta, 'the build box should show the estimated time left');
  assert(sawWord, 'the build box should show a status word while building');
  assert(!sawStep, "the build box should not show Blender's step names");
  await sleep(2500);
  assert.equal(await ev(`document.getElementById('bfun').hidden`), true, 'status words should stop when the build is done');
  assert.match(await ev(`document.getElementById('bmsg').textContent`), /built in \d+ (s|min)/, 'the build box should say how long the build took');
  const plan = await (await fetch(`${base}/jobs/${job}/plan.json`)).json();
  assert.strictEqual(plan.furnish, false, 'plan.furnish should be false after unticking');
  // reopening the page must show the saved choice
  await cdp('Page.navigate', { url: `${base}/web/edit.html?job=${job}` });
  for (let i = 0; i < 150 && (await ev(`getComputedStyle(document.getElementById('wait')).display`)) !== 'none'; i++) await sleep(200);
  assert.equal(await ev(`document.getElementById('furn').checked`), false, 'Furniture box should stay unticked after reload');
  // the furniture models page opens inside the review page
  await ev(`document.getElementById('models').click()`);
  let cards = 0;
  for (let i = 0; i < 50 && !cards; i++) { await sleep(200); cards = await ev(`document.getElementById('modelsframe').contentDocument?.querySelectorAll('#list figure').length || 0`); }
  assert(cards >= 10 && await ev(`document.getElementById('modelsdlg').open`), 'Change furniture models should show the models in a dialog');
  assert.equal(await ev(`!!document.getElementById('modelsframe').contentDocument.getElementById('brand')`), false, 'no Home link inside the dialog');
  await ev(`document.getElementById('modelsdlg').close()`);
  // walkthrough: screenshot (P) and recording (R) land in the downloads folder
  const dl = fs.mkdtempSync(path.join(os.tmpdir(), 'planto3d-'));
  const key = async (code, vk) => { for (const type of ['keyDown', 'keyUp']) await cdp('Input.dispatchKeyEvent', { type, code, key: code.slice(3).toLowerCase(), windowsVirtualKeyCode: vk }); };
  await cdp('Page.setDownloadBehavior', { behavior: 'allow', downloadPath: dl });
  await cdp('Emulation.setDeviceMetricsOverride', { width: 1280, height: 720, deviceScaleFactor: 1, mobile: false });
  const meta = await (await fetch(`${base}/jobs/${job}/meta.json`)).json();
  const start = entrance(meta);
  await cdp('Page.navigate', { url: `${base}/web/view.html?job=${job}&pose=${start.x},${start.y},0,30,0` });
  for (let i = 0; i < 300 && !(await ev('!!window.__ready')); i++) await sleep(200);
  await sleep(1500);
  await key('KeyP', 80);
  await sleep(2500);
  await key('KeyR', 82);
  await cdp('Input.dispatchKeyEvent', { type: 'keyDown', code: 'KeyE', key: 'e', windowsVirtualKeyCode: 69 });   // turn: a still view compresses to almost nothing
  await sleep(3000);
  await cdp('Input.dispatchKeyEvent', { type: 'keyUp', code: 'KeyE', key: 'e', windowsVirtualKeyCode: 69 });
  assert.match(await ev(`document.getElementById('rec').textContent`), /^Stop 0:0\d$/, 'Record button should show the running time');
  await key('KeyR', 82);
  await sleep(2500);
  // the map: drawn, M enlarges it; leaving the top view (T, T) must not leave the mouse uncaptured with no start screen
  assert(await ev(`(() => { const c = document.getElementById('map'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n; })()`) > 1000, 'the map should be drawn');
  await key('KeyM', 77);
  assert.equal(await ev(`document.getElementById('map').classList.contains('big')`), true, 'M should enlarge the map');
  await key('KeyM', 77);
  await key('KeyT', 84);
  await sleep(400);
  await key('KeyT', 84);
  await sleep(600);
  assert.equal(await ev(`!!document.pointerLockElement || getComputedStyle(document.getElementById('overlay')).display !== 'none'`), true,
    'leaving the top view should capture the mouse again or show the start screen');
  const files = fs.readdirSync(dl), png = files.find((f) => f.endsWith('.png')), vid = files.find((f) => /\.(mp4|webm)$/.test(f));
  assert(png && vid, `expected a screenshot and a video, got ${files}`);
  const ihdr = fs.readFileSync(path.join(dl, png));
  assert(ihdr.readUInt32BE(16) * ihdr.readUInt32BE(20) >= 0.95 * 3840 * 2160, 'screenshot should be about 4K');
  assert(fs.statSync(path.join(dl, vid)).size > 100e3, 'recording should not be empty');
  fs.rmSync(dl, { recursive: true });
  console.log('PASS upload page, furniture option, furniture models dialog, build box, screenshot, recording, map and top view');
} finally {
  ch.kill();
  if (job) fs.rmSync(new URL(`../jobs/${job}`, import.meta.url), { recursive: true, force: true });   // the test's own upload
}
process.exit(0);
