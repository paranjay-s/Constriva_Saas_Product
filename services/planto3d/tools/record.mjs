// Record a walkthrough from the viewer: node tools/record.mjs <job> <frames.json> <out_dir> [http://127.0.0.1:8080]
// Needs a Chromium / Chrome binary: set CHROME to its path (default: chromium on PATH).
// Headless Chromium on the GPU (ANGLE over EGL); each frame is drawn by window.__frame and saved as JPEG.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const [job, framesFile, out, base = 'http://127.0.0.1:8080'] = process.argv.slice(2);
const frames = JSON.parse(fs.readFileSync(framesFile, 'utf8'));
const CH = process.env.CHROME || 'chromium';
// WebGL backend of the headless browser: EGL on Linux, Metal on a Mac (set ANGLE to choose another)
const ANGLE = process.env.ANGLE || (process.platform === 'darwin' ? 'metal' : 'gl-egl');
const port = 9400 + Math.floor(Math.random() * 400);
const ch = spawn(CH, ['--headless=new', '--no-sandbox', `--remote-debugging-port=${port}`, '--window-size=1280,720',
  '--hide-scrollbars', `--use-angle=${ANGLE}`, '--ignore-gpu-blocklist', '--enable-gpu', 'about:blank'], { stdio: 'ignore' });
const sleep = (t) => new Promise((r) => setTimeout(r, t));
let targets;
for (let i = 0; i < 100 && !targets; i++) { try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); } catch { await sleep(200); } }
const ws = new WebSocket(targets.find((t) => t.type === 'page').webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r));
let id = 0; const pend = new Map();
ws.addEventListener('message', (e) => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } });
const cdp = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => (await cdp('Runtime.evaluate', { expression: expr, returnByValue: true })).result?.result?.value;
const [x0, y0] = frames[0];
await cdp('Page.navigate', { url: `${base}/web/view.html?job=${job}&pose=${x0},${y0},0,0,0` });
for (let i = 0; i < 600 && !(await ev('!!window.__ready')); i++) await sleep(200);
console.log('renderer', await ev(`(() => { const g = document.createElement('canvas').getContext('webgl2'); const d = g.getExtension('WEBGL_debug_renderer_info'); return g.getParameter(d.UNMASKED_RENDERER_WEBGL); })()`));
// exact 1280x720 drawing size (headless window chrome eats some of --window-size)
await cdp('Emulation.setDeviceMetricsOverride', { width: 1280, height: 720, deviceScaleFactor: 1, mobile: false });
await ev('dispatchEvent(new Event("resize"))');
await sleep(1500);                                   // textures finish uploading
fs.mkdirSync(out, { recursive: true });
const t0 = Date.now();
for (let i = 0; i < frames.length; i++) {
  const [x, y, yaw, pitch] = frames[i];
  const url = await ev(`__frame(${x}, ${y}, 0, ${yaw}, ${pitch})`);
  if (!url) throw new Error(`frame ${i} failed`);
  fs.writeFileSync(`${out}/f_${String(i).padStart(5, '0')}.jpg`, Buffer.from(url.split(',')[1], 'base64'));
  if (i % 500 === 0) console.log(`frame ${i}/${frames.length}  ${((Date.now() - t0) / 1000).toFixed(0)} s`);
}
console.log(`done ${frames.length} frames in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
ch.kill();
process.exit(0);
