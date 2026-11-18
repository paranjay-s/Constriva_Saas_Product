// Walkthrough of a generated house: baked lighting (light maps) on unlit materials, so it runs on any GPU.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import * as walk from './walk.js';
import { plan as tourPlan } from './tour.js';

const $ = (id) => document.getElementById(id);
const job = new URLSearchParams(location.search).get('job');
const base = `../jobs/${job}/`;
const WALK = 1.5, RUN = 3.0;

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.AgXToneMapping;
renderer.toneMappingExposure = 1.0;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xbfd6ea);
scene.fog = new THREE.Fog(0xbfd6ea, 60, 160);
const camera = new THREE.PerspectiveCamera(70, innerWidth / innerHeight, 0.05, 400);
const env = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;

const meta = await fetch(base + 'meta.json').then((r) => r.json());
const draco = new DRACOLoader().setDecoderPath('../three/examples/jsm/libs/draco/');
const gltf = await new GLTFLoader().setDRACOLoader(draco).loadAsync(base + 'house.glb', (e) => {
  if (e.total) $('status').textContent = `Loading model… ${Math.round(100 * e.loaded / e.total)}%`;
});
const texLoader = new THREE.TextureLoader();
const lightmaps = {};
await Promise.all(Object.entries(meta.lightmaps || {}).map(async ([name, file]) => {
  const t = await texLoader.loadAsync(base + file);
  t.channel = 1;                       // second UV set (TEXCOORD_1)
  t.colorSpace = THREE.SRGBColorSpace;  // stored sRGB-encoded for precision in the shadows
  t.flipY = false;
  lightmaps[name] = t;
}));

// ---- materials: unlit * baked light; real-time light only for objects without a light map (trees)
const baked = !!meta.baked;
if (!baked) {
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7a66, 1.6));
  const sun = new THREE.DirectionalLight(0xfff1d6, 2.2);
  sun.position.set(-8, 14, 6);
  scene.add(sun);
} else {
  scene.add(new THREE.HemisphereLight(0xdfefff, 0x6d6450, 1.2));
  const sun = new THREE.DirectionalLight(0xfff1d6, 1.6);
  sun.position.set(-8, 14, 6);
  scene.add(sun);
}
const levels = [];   // level index -> objects (hidden above the current level in top view)
gltf.scene.traverse((o) => {
  if (!o.isMesh) return;
  let root = o;
  while (root.parent && root.parent !== gltf.scene) root = root.parent;
  const lm = lightmaps[root.name] || lightmaps[o.name];
  const lmax = (meta.lightmap_max || {})[root.name] ?? (meta.lightmap_max || {})[o.name] ?? 1;
  const conv = (m) => {
    const emissive = m.emissive && (m.emissive.r + m.emissive.g + m.emissive.b) > 0.01;
    const opts = { map: m.map, color: m.color, transparent: m.transparent, opacity: m.opacity, side: m.side,
                   alphaTest: m.alphaTest, depthWrite: !m.transparent };
    if (emissive) return new THREE.MeshBasicMaterial({ color: m.emissive.clone().multiplyScalar(Math.max(1, m.emissiveIntensity || 1)) });
    if (m.transparent) return new THREE.MeshBasicMaterial({ ...opts, envMap: env, reflectivity: 0.12, combine: THREE.MixOperation });
    // mirrors are pure metal: the baked (diffuse) light is black there, so show only the reflection
    if (m.metalness > 0.9 && m.roughness < 0.1) return new THREE.MeshBasicMaterial({ color: 0xe8ecef, envMap: env, reflectivity: 0.9, combine: THREE.MixOperation });
    if (lm) {
      const shiny = m.metalness > 0.5 ? 0.55 : m.roughness < 0.25 ? 0.12 : 0;
      return new THREE.MeshBasicMaterial({ ...opts, lightMap: lm, lightMapIntensity: Math.PI * lmax,
                                           envMap: shiny ? env : null, reflectivity: shiny, combine: THREE.MixOperation });
    }
    return new THREE.MeshLambertMaterial(opts);
  };
  o.material = Array.isArray(o.material) ? o.material.map(conv) : conv(o.material);
  const m = /^bake_level_(\d+)/.exec(root.name) || /_(\d+)$/.exec(root.name);
  if (m && /^(bake_level|glass)/.test(root.name)) (levels[+m[1]] ||= []).push(o);
});
scene.add(gltf.scene);

// ---- plan (x, y metres, z up) -> three (x, z, -y)
const W = (x, y, z) => new THREE.Vector3(x, z, -y);
const floors = meta.floors;
const roomAt = (lv, x, y) => walk.roomAt(meta, lv, x, y);

// ---- player
const p = { ...walk.entrance(meta), z: floors[0].z, yaw: 0, pitch: 0 };
const keys = {};
let locked = false, topView = false;
addEventListener('keydown', (e) => {
  keys[e.code] = true;
  if (e.code === 'KeyT') toggleTop();
  if (e.code === 'KeyP' && !e.repeat) screenshot();
  if (e.code === 'KeyR' && !e.repeat) toggleRec();
  if (e.code === 'KeyM' && !e.repeat) toggleMap();
});
addEventListener('keyup', (e) => { keys[e.code] = false; });

// ---- guided tour (tour.js): walks the route at 1 m/s with eased turns, pausing in the main rooms; any movement key,
// a mouse button or a touch hands control back
let tour = null;
const TOUR_SPEED = 1.0, TURN = 2.5;
function startTour() {
  const route = tourPlan(meta);
  if (route.length < 2) return;
  Object.assign(p, { x: route[0].x, y: route[0].y, z: route[0].z, pitch: -0.05 });
  tour = { route, i: 1, wait: 0 };
  $('tourbtn').textContent = 'Stop tour';
}
function stopTour() { tour = null; $('tourbtn').textContent = 'Guided tour'; }
function tourStep(dt) {
  if (tour.wait > 0) { tour.wait -= dt; return; }
  const t = tour.route[tour.i];
  if (!t) { stopTour(); return; }
  const dx = t.x - p.x, dy = t.y - p.y, d = Math.hypot(dx, dy);
  if (d > 0.05) {      // plan axes: yaw 0 looks along +y; heading to (dx, dy) is atan2(-dx, dy)
    const want = Math.atan2(-dx, dy);
    let turn = want - p.yaw;
    turn = Math.atan2(Math.sin(turn), Math.cos(turn));
    p.yaw += turn * Math.min(1, TURN * dt);
    const step = Math.min(d, TOUR_SPEED * dt * (Math.abs(turn) > 1.2 ? 0.3 : 1));
    if (t.stair) { p.x += dx / d * step; p.y += dy / d * step; p.z += (t.z - p.z) * Math.min(1, step / d); }
    else { p.x += dx / d * step; p.y += dy / d * step; p.z = t.z; }
  } else {
    if (t.pause) tour.wait = t.pause;
    tour.i++;
  }
}
for (const code of ['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'])
  addEventListener('keydown', (e) => { if (e.code === code && tour) stopTour(); });
const canvas = renderer.domElement;
$('overlay').addEventListener('click', () => {
  if (matchMedia('(pointer: coarse)').matches) { $('overlay').style.display = 'none'; return; }
  canvas.requestPointerLock();
});
document.addEventListener('pointerlockchange', () => {
  locked = document.pointerLockElement === canvas;
  $('overlay').style.display = locked || topView ? 'none' : 'flex';
});
// the browser refused to capture the mouse: show the start screen, whose click captures it
document.addEventListener('pointerlockerror', () => { if (!topView) $('overlay').style.display = 'flex'; });
addEventListener('mousemove', (e) => {
  if (!locked) return;
  p.yaw -= e.movementX * 0.0022;
  p.pitch = Math.max(-1.4, Math.min(1.4, p.pitch - e.movementY * 0.0022));
});
// touch: left half = move stick, right half = look
const touch = { move: null, look: null, mx: 0, my: 0 };
canvas.addEventListener('touchstart', (e) => {
  for (const t of e.changedTouches) {
    if (t.clientX < innerWidth / 2 && !touch.move) touch.move = { id: t.identifier, x: t.clientX, y: t.clientY };
    else if (!touch.look) touch.look = { id: t.identifier, x: t.clientX, y: t.clientY };
  }
}, { passive: true });
canvas.addEventListener('touchmove', (e) => {
  if (topView) return;
  for (const t of e.changedTouches) {
    if (touch.move && t.identifier === touch.move.id) {
      touch.mx = Math.max(-1, Math.min(1, (t.clientX - touch.move.x) / 60));
      touch.my = Math.max(-1, Math.min(1, (t.clientY - touch.move.y) / 60));
    } else if (touch.look && t.identifier === touch.look.id) {
      p.yaw -= (t.clientX - touch.look.x) * 0.005;
      p.pitch = Math.max(-1.4, Math.min(1.4, p.pitch - (t.clientY - touch.look.y) * 0.005));
      touch.look.x = t.clientX; touch.look.y = t.clientY;
    }
  }
}, { passive: true });
canvas.addEventListener('touchend', (e) => {
  for (const t of e.changedTouches) {
    if (touch.move && t.identifier === touch.move.id) { touch.move = null; touch.mx = touch.my = 0; }
    if (touch.look && t.identifier === touch.look.id) touch.look = null;
  }
});

// ---- top view (dollhouse): storeys above the chosen one are hidden
const orbit = new OrbitControls(camera, canvas);
orbit.enabled = false;
let showLevel = 0;
function showLevels(n) {
  showLevel = n;
  levels.forEach((objs, i) => objs?.forEach((o) => { o.visible = !topView || i <= n; }));
  document.querySelectorAll('#floors button').forEach((b, i) => b.classList.toggle('on', topView && i === n));
}
function toggleTop() {
  topView = !topView;
  if (topView) {
    document.exitPointerLock?.();
    $('overlay').style.display = 'none';
    const b = meta.bounds, cx = (b[0] + b[1]) / 2, cy = (b[2] + b[3]) / 2, size = Math.max(b[1] - b[0], b[3] - b[2]);
    const z0 = floors[walk.levelOf(meta, p.z)].z;
    orbit.target.copy(W(cx, cy, z0));
    camera.position.copy(W(cx, cy - size * 0.75, z0 + size * 1.05));
    orbit.enabled = true;
    orbit.update();
    showLevels(walk.levelOf(meta, p.z));
  } else {
    orbit.enabled = false;
    showLevels(levels.length);
    // back to walking: capture the mouse again, or looking around stays dead with nothing to click
    if (!matchMedia('(pointer: coarse)').matches) canvas.requestPointerLock()?.catch?.(() => { $('overlay').style.display = 'flex'; });
  }
  map.style.display = topView ? 'none' : 'block';
  $('cross').style.display = topView ? 'none' : 'block';
  $('topbtn').textContent = topView ? 'Walk' : 'Top view';
}
$('topbtn').onclick = toggleTop;
$('tourbtn').onclick = () => (tour ? stopTour() : startTour());
canvas.addEventListener('pointerdown', () => { if (tour) stopTour(); });
floors.forEach((f, i) => {
  const b = document.createElement('button');
  b.textContent = f.name;
  b.onclick = () => {
    if (topView) { showLevels(i); orbit.target.y = f.z; return; }
    // walk mode: jump to a free spot in the biggest room of that floor
    const r = (f.rooms.filter((q) => !['open', 'garden', 'yard', 'stair'].includes(q.type))
      .flatMap((q) => q.rects).sort((a, c) => (c[1] - c[0]) * (c[3] - c[2]) - (a[1] - a[0]) * (a[3] - a[2])))[0];
    if (r) { p.x = (r[0] + r[1]) / 2; p.y = (r[2] + r[3]) / 2; p.z = f.z; }
  };
  $('floors').appendChild(b);
});

// ---- map (M): the storey you are on from above, with room names, stairs, and where you stand and look
const map = $('map'), mg = map.getContext('2d');
// water (pool, water body, dock) is blue on the map and in the top view (web/rooms.json kinds)
const WATER = new Set(['pool', 'water', 'dock']);
const OUTSIDE = new Set(['open', 'garden', 'yard', 'balcony', 'parking']);
const roomName = (r) => (r.label || r.type).split(/\s+/).filter((w) => !/\d/.test(w)).join(' ').toUpperCase() || r.type.toUpperCase();   // without the size
let mapBig = false;
function toggleMap() { mapBig = !mapBig; map.classList.toggle('big', mapBig); document.body.classList.toggle('mapbig', mapBig); }
map.onclick = toggleMap;
function drawMap(lv) {
  const dpr = devicePixelRatio || 1, w = map.clientWidth, h = map.clientHeight;
  if (map.width !== Math.round(w * dpr) || map.height !== Math.round(h * dpr)) { map.width = Math.round(w * dpr); map.height = Math.round(h * dpr); }
  mg.setTransform(dpr, 0, 0, dpr, 0, 0);
  mg.clearRect(0, 0, w, h);
  const f = floors[lv], pad = mapBig ? 46 : 10, rs = [...f.colliders, ...f.rooms.flatMap((r) => r.rects)];
  const x0 = Math.min(...rs.map((r) => r[0])), x1 = Math.max(...rs.map((r) => r[1]));
  const y0 = Math.min(...rs.map((r) => r[2])), y1 = Math.max(...rs.map((r) => r[3]));
  const k = Math.min((w - 2 * pad) / (x1 - x0), (h - 2 * pad) / (y1 - y0));
  const X = (x) => (w - (x1 - x0) * k) / 2 + (x - x0) * k, Y = (y) => (h + (y1 - y0) * k) / 2 - (y - y0) * k;   // plan +y is up
  const box = (r) => mg.fillRect(X(r[0]), Y(r[3]), (r[1] - r[0]) * k, (r[3] - r[2]) * k);
  const here = f.rooms.find((r) => r.rects.some((q) => walk.inRect(q, p.x, p.y)));
  // an upper storey is drawn only where it has a floor: a void or a yard open to the storey below stays dark
  mg.save();
  if (f.floor) { mg.beginPath(); [...f.floor, ...(f.stairs || []).map((s) => s.rect)].forEach((r) => mg.rect(X(r[0]), Y(r[3]), (r[1] - r[0]) * k, (r[3] - r[2]) * k)); mg.clip(); }
  for (const r of f.rooms) {
    mg.fillStyle = r === here ? 'rgba(224, 122, 72, .5)' : WATER.has(r.type) ? 'rgba(74, 163, 223, .75)'
      : OUTSIDE.has(r.type) ? 'rgba(120, 170, 110, .22)' : 'rgba(255, 255, 255, .13)';
    r.rects.forEach(box);
  }
  mg.restore();
  mg.fillStyle = 'rgba(196, 154, 108, .85)';
  (f.stairs || []).forEach((s) => box(s.rect));
  mg.fillStyle = 'rgba(255, 255, 255, .85)';
  f.colliders.forEach(box);
  const size = mapBig ? 13 : 9;
  mg.font = `600 ${size}px system-ui, sans-serif`;
  mg.textAlign = 'center';
  mg.textBaseline = 'middle';
  mg.fillStyle = '#fff';
  for (const r of f.rooms) {            // a name is drawn only where it fits inside its room
    const q = r.rects.reduce((a, b) => ((b[1] - b[0]) * (b[3] - b[2]) > (a[1] - a[0]) * (a[3] - a[2]) ? b : a));
    const name = roomName(r);
    if (mg.measureText(name).width < (q[1] - q[0]) * k - 2 && size < (q[3] - q[2]) * k - 2) mg.fillText(name, X((q[0] + q[1]) / 2), Y((q[2] + q[3]) / 2));
  }
  // you: a view cone and a dot (yaw 0 looks along plan +y, turning left is positive)
  const px = X(p.x), py = Y(p.y), a = -Math.PI / 2 - p.yaw, len = mapBig ? 70 : 30;
  const cone = mg.createRadialGradient(px, py, 0, px, py, len);
  cone.addColorStop(0, 'rgba(255, 220, 190, .75)');
  cone.addColorStop(1, 'rgba(255, 220, 190, 0)');
  mg.fillStyle = cone;
  mg.beginPath(); mg.moveTo(px, py); mg.arc(px, py, len, a - 0.6, a + 0.6); mg.closePath(); mg.fill();
  mg.fillStyle = '#e07a48'; mg.strokeStyle = '#fff'; mg.lineWidth = 1.5;
  mg.beginPath(); mg.arc(px, py, mapBig ? 6 : 4, 0, 7); mg.fill(); mg.stroke();
  if (mapBig) {
    mg.fillStyle = '#fff';
    mg.textAlign = 'left';
    mg.font = '600 15px system-ui, sans-serif';
    mg.fillText([f.name, here && roomName(here)].filter(Boolean).join(' · '), 18, 22);
    mg.textAlign = 'right';
    mg.font = '13px system-ui, sans-serif';
    mg.fillStyle = 'rgba(255, 255, 255, .6)';
    mg.fillText('M to close', w - 18, 22);
  }
}

// ---- screenshot (P) and video recording (R): the 3D view only, without the buttons and labels
function save(blob, ext) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);      // local time in the file name
  a.download = `walkthrough-${now.toISOString().slice(0, 19).replace(/[T:]/g, '-')}.${ext}`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 10000);
}
let rec = null;
function screenshot() {
  const pr = renderer.getPixelRatio();
  // about 4K worth of pixels, whatever the window size (not while recording: the video must keep one size)
  if (!rec) renderer.setPixelRatio(Math.max(pr, Math.sqrt(3840 * 2160 / (innerWidth * innerHeight))));
  renderer.render(scene, camera);          // the picture can only be read right after a render
  canvas.toBlob((b) => save(b, 'png'), 'image/png');
  renderer.setPixelRatio(pr);
}
const REC_TYPE = window.MediaRecorder && ['video/mp4;codecs=avc1.42E01E', 'video/webm;codecs=vp9', 'video/webm']
  .find((t) => MediaRecorder.isTypeSupported(t));
function toggleRec() {
  if (!REC_TYPE) return;
  if (rec) return rec.stop();
  const chunks = [], t0 = performance.now();
  const label = () => {
    const s = Math.floor((performance.now() - t0) / 1000);
    $('rec').textContent = `Stop ${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  };
  rec = new MediaRecorder(canvas.captureStream(30), { mimeType: REC_TYPE, videoBitsPerSecond: 12e6 });
  rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  const tick = setInterval(label, 500);
  rec.onstop = () => {
    clearInterval(tick);
    rec = null;
    $('rec').textContent = 'Record';
    $('rec').classList.remove('live');
    const blob = new Blob(chunks, { type: REC_TYPE });
    if (REC_TYPE.includes('mp4')) return save(blob, 'mp4');
    $('rec').textContent = 'Converting…';      // this browser records WebM: the server turns it into MP4
    fetch('../api/mp4', { method: 'POST', body: blob }).then((r) => (r.ok ? r.blob() : Promise.reject()))
      .then((mp4) => save(mp4, 'mp4'), () => save(blob, 'webm'))        // (no ffmpeg on the server: keep the WebM)
      .finally(() => { $('rec').textContent = 'Record'; });
  };
  rec.start(1000);
  $('rec').classList.add('live');
  label();
}
$('blend').onclick = async () => {        // the server packs the textures into one .blend (a few seconds, once per build)
  const b = $('blend');
  b.disabled = true;
  b.textContent = 'Preparing…';
  try {
    const r = await fetch(`../api/jobs/${job}/export`, { method: 'POST' }), j = await r.json();
    if (!r.ok) throw new Error(j.error);
    const a = document.createElement('a');
    a.href = '..' + j.url;        // the server answers /jobs/…: keep it under this page's own prefix
    a.download = 'house-blender.zip';
    a.click();
  } catch (e) { alert(e.message || 'Could not prepare the Blender file.'); }
  b.disabled = false;
  b.textContent = 'Blender file';
};
$('shot').onclick = screenshot;
$('rec').onclick = toggleRec;
$('rec').hidden = !REC_TYPE;               // this browser cannot record video

// ---- loop
const clock = new THREE.Clock();
let frames = 0, fpsT = 0;
renderer.setAnimationLoop(() => {
  const raw = clock.getDelta(), dt = Math.min(raw, 0.05);
  frames++; fpsT += raw;
  if (fpsT > 0.5) { $('fps').textContent = `${Math.round(frames / fpsT)} fps`; frames = 0; fpsT = 0; }
  if (tour && !topView) tourStep(dt);
  if (!topView) {
    const sp = (keys.ShiftLeft || keys.ShiftRight ? RUN : WALK) * dt;
    let f = 0, s = 0;
    if (keys.KeyW || keys.ArrowUp) f += 1;
    if (keys.KeyS || keys.ArrowDown) f -= 1;
    if (keys.KeyD || keys.ArrowRight) s += 1;
    if (keys.KeyA || keys.ArrowLeft) s -= 1;
    f -= touch.my; s += touch.mx;
    if (keys.KeyQ) p.yaw += 1.8 * dt;
    if (keys.KeyE) p.yaw -= 1.8 * dt;
    const len = Math.hypot(f, s);
    if (len > 0.01) {
      const k = sp / Math.max(1, len);
      // plan axes: yaw 0 looks along +y (three -z)
      const dx = (-Math.sin(p.yaw) * f + Math.cos(p.yaw) * s) * k;
      const dy = (Math.cos(p.yaw) * f + Math.sin(p.yaw) * s) * k;
      walk.move(meta, p, dx, dy);
    }
    camera.position.copy(W(p.x, p.y, p.z + meta.eye));
    camera.rotation.set(0, 0, 0);
    camera.rotation.order = 'YXZ';
    camera.rotation.y = p.yaw;
    camera.rotation.x = p.pitch;
    const lv = walk.levelOf(meta, p.z);
    $('room').textContent = [floors[lv].name, roomAt(lv, p.x, p.y)].filter(Boolean).join(' · ');
    drawMap(lv);
  } else orbit.update();
  renderer.render(scene, camera);
});
$('status').textContent = matchMedia('(pointer: coarse)').matches ? 'Tap to start' : 'Click to walk in';
// ?pose=x,y,level,yawDeg,pitchDeg (metres) and ?top=level : fixed views for previews / tests
const q = new URLSearchParams(location.search);
if (q.get('pose')) {
  const [x, y, lv, yaw, pitch] = q.get('pose').split(',').map(Number);
  Object.assign(p, { x, y, z: floors[lv || 0].z, yaw: (yaw || 0) * Math.PI / 180, pitch: (pitch || 0) * Math.PI / 180 });
  $('overlay').style.display = 'none';
}
if (q.get('top') !== null) { toggleTop(); showLevels(+q.get('top') || 0); }
if (q.get('embed') !== null) $('newplan').remove();        // inside another site's page there is no "new plan" to go to
// recording hook: draw one frame at a pose (metres, radians) and return it as a JPEG data URL
window.__frame = (x, y, z, yaw, pitch) => {
  renderer.setAnimationLoop(null);
  camera.position.copy(W(x, y, z + meta.eye));
  camera.rotation.order = 'YXZ';
  camera.rotation.set(pitch, yaw, 0);
  renderer.render(scene, camera);
  return renderer.domElement.toDataURL('image/jpeg', 0.92);
};
window.__ready = true;
addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

// a fresh embed token from the framing page (it refreshes the token before it runs out): the page's own address
// takes the new token in place, so every later request (relative URLs) carries it; nothing reloads
addEventListener('message', (e) => {
  const d = e.data;
  if (e.source !== parent || !d || d.source !== 'planto3d-host' || d.type !== 'token' || typeof d.base !== 'string') return;
  if (!/^\/api\/v1\/3d\/embed\/[A-Za-z0-9_.-]+$/.test(d.base)) return;
  const at = location.pathname.indexOf('/web/');
  if (at > 0) history.replaceState(history.state, '', d.base + location.pathname.slice(at) + location.search);
});
