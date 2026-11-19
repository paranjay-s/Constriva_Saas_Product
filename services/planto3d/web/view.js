// Walkthrough of a generated house: baked lighting (light maps) on unlit materials, so it runs on any GPU.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import * as walk from './walk.js';
import { plan as tourPlan } from './tour.js';
// opened from a share link: view only (the link reaches no writes, and no Blender file)
const SHARED = new URLSearchParams(location.search).has('shared');

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
let liveHemi = null, liveSun = null;   // light for what is not baked (trees): dimmed in the evening
if (!baked) {
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7a66, 1.6));
  const sun = new THREE.DirectionalLight(0xfff1d6, 2.2);
  sun.position.set(-8, 14, 6);
  scene.add(sun);
} else {
  liveHemi = new THREE.HemisphereLight(0xdfefff, 0x6d6450, 1.2);
  scene.add(liveHemi);
  liveSun = new THREE.DirectionalLight(0xfff1d6, 1.6);
  liveSun.position.set(-8, 14, 6);
  scene.add(liveSun);
}
const levels = [];   // level index -> objects (hidden above the current level in top view)
const lit = [];      // materials with a light map: the Day / Evening switch swaps their maps
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
      const mat = new THREE.MeshBasicMaterial({ ...opts, lightMap: lm, lightMapIntensity: Math.PI * lmax,
                                                envMap: shiny ? env : null, reflectivity: shiny, combine: THREE.MixOperation });
      lit.push({ mat, names: [root.name, o.name] });
      return mat;
    }
    return new THREE.MeshLambertMaterial(opts);
  };
  o.material = Array.isArray(o.material) ? o.material.map(conv) : conv(o.material);
  const m = /^bake_level_(\d+)/.exec(root.name) || /_(\d+)$/.exec(root.name);
  if (m && /^(bake_level|glass)/.test(root.name)) (levels[+m[1]] ||= []).push(o);
});
scene.add(gltf.scene);

// ---- Day / Evening: a second set of light maps baked with dusk light (meta.lightmaps_evening), loaded on first use
const dayBtn = $('daybtn');
let evening = false, eveningMaps = null;
if (!meta.lightmaps_evening) dayBtn.remove();
else dayBtn.onclick = async () => {
  if (!eveningMaps) {
    dayBtn.disabled = true;
    dayBtn.textContent = 'Loading…';
    eveningMaps = {};
    await Promise.all(Object.entries(meta.lightmaps_evening).map(async ([name, file]) => {
      const t = await texLoader.loadAsync(base + file);
      t.channel = 1; t.colorSpace = THREE.SRGBColorSpace; t.flipY = false;
      eveningMaps[name] = t;
    }));
    dayBtn.disabled = false;
  }
  evening = !evening;
  const maps = evening ? eveningMaps : lightmaps;
  const most = (evening ? meta.lightmap_max_evening : meta.lightmap_max) || {};
  for (const { mat, names } of lit) {
    const n = names.find((k) => maps[k]);
    if (!n) continue;
    mat.lightMap = maps[n];
    mat.lightMapIntensity = Math.PI * (most[n] ?? 1);
  }
  if (liveHemi) liveHemi.intensity = evening ? 0.25 : 1.2;
  if (liveSun) { liveSun.intensity = evening ? 0.15 : 1.6; liveSun.color.setHex(evening ? 0xffa060 : 0xfff1d6); }
  const sky = evening ? 0x1b2338 : 0xbfd6ea;
  scene.background.setHex(sky);
  scene.fog.color.setHex(sky);
  dayBtn.textContent = evening ? 'Day' : 'Evening';
  dayBtn.title = evening ? 'Daylight' : 'Evening light (lamps on, dusk outside)';
};

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
  if (t.jump) {        // a part of the house the tour cannot walk to (tour.js): there at once
    Object.assign(p, { x: t.x, y: t.y, z: t.z });
    if (t.pause) tour.wait = t.pause;
    tour.i++;
    return;
  }
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
const OUTSIDE = new Set(['open', 'garden', 'yard', 'balcony', 'parking', 'court', 'custom']);
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
  // blueprint grid: a fine line every metre, a stronger one every 5 m (when they are far enough apart)
  if (k >= 4) {
    for (let m = Math.ceil(x0); m <= x1; m++) {
      mg.fillStyle = m % 5 ? 'rgba(190, 220, 255, .08)' : 'rgba(190, 220, 255, .18)';
      mg.fillRect(Math.round(X(m)), 0, 1, h);
    }
    for (let m = Math.ceil(y0); m <= y1; m++) {
      mg.fillStyle = m % 5 ? 'rgba(190, 220, 255, .08)' : 'rgba(190, 220, 255, .18)';
      mg.fillRect(0, Math.round(Y(m)), w, 1);
    }
  }
  const outline = (r) => mg.strokeRect(X(r[0]) + 0.5, Y(r[3]) + 0.5, (r[1] - r[0]) * k - 1, (r[3] - r[2]) * k - 1);
  // an upper storey is drawn only where it has a floor: a void or a yard open to the storey below stays dark
  mg.save();
  if (f.floor) { mg.beginPath(); [...f.floor, ...(f.stairs || []).map((s) => s.rect)].forEach((r) => mg.rect(X(r[0]), Y(r[3]), (r[1] - r[0]) * k, (r[3] - r[2]) * k)); mg.clip(); }
  mg.lineWidth = 1;
  for (const r of f.rooms) {
    mg.fillStyle = r === here ? 'rgba(255, 170, 110, .35)' : WATER.has(r.type) ? 'rgba(120, 205, 255, .55)'
      : OUTSIDE.has(r.type) ? 'rgba(160, 230, 170, .10)' : 'rgba(255, 255, 255, .07)';
    r.rects.forEach(box);
    mg.strokeStyle = r.type === 'custom' ? 'rgba(255, 170, 70, .9)' : 'rgba(220, 238, 255, .35)';
    mg.setLineDash(OUTSIDE.has(r.type) ? [3, 3] : []);
    r.rects.forEach(outline);
  }
  mg.setLineDash([]);
  mg.restore();
  // stairs: an outline with treads
  mg.strokeStyle = 'rgba(235, 245, 255, .8)';
  for (const s of f.stairs || []) {
    outline(s.rect);
    if (s.landing) continue;
    const [a0, a1, b0, b1] = s.axis === 'x' ? [s.rect[0], s.rect[1], s.rect[2], s.rect[3]] : [s.rect[2], s.rect[3], s.rect[0], s.rect[1]];
    for (let t = a0 + 0.28; t < a1; t += 0.28) {
      mg.beginPath();
      if (s.axis === 'x') { mg.moveTo(X(t), Y(b0)); mg.lineTo(X(t), Y(b1)); } else { mg.moveTo(X(b0), Y(t)); mg.lineTo(X(b1), Y(t)); }
      mg.stroke();
    }
  }
  // walls in white; a larger blocked area (water, a closed shaft) only outlined and hatched, so its colour shows
  mg.fillStyle = 'rgba(245, 250, 255, .95)';
  for (const c of f.colliders) {
    if (Math.min(c[1] - c[0], c[3] - c[2]) <= 0.6) { box(c); continue; }
    mg.save();
    mg.beginPath(); mg.rect(X(c[0]), Y(c[3]), (c[1] - c[0]) * k, (c[3] - c[2]) * k); mg.clip();
    mg.strokeStyle = 'rgba(220, 238, 255, .3)';
    for (let t = -h; t < w; t += 7) { mg.beginPath(); mg.moveTo(t, h); mg.lineTo(t + h, 0); mg.stroke(); }
    mg.restore();
    mg.strokeStyle = 'rgba(235, 245, 255, .7)';
    outline(c);
  }
  // scale bar: 5 m (or 1 m on a small plan), bottom right
  const bar = (x1 - x0) > 8 ? 5 : 1, bx = w - pad - bar * k, by = h - pad / 2 - 4;
  if (bar * k > 12 && bar * k < w / 2) {
    mg.fillStyle = 'rgba(235, 245, 255, .85)';
    mg.fillRect(bx, by, bar * k, 2); mg.fillRect(bx, by - 4, 1.5, 6); mg.fillRect(bx + bar * k - 1.5, by - 4, 1.5, 6);
    mg.font = `${mapBig ? 12 : 9}px ui-monospace, Menlo, monospace`; mg.textAlign = 'center'; mg.textBaseline = 'bottom';
    mg.fillText(`${bar} m`, bx + bar * k / 2, by - 3);
  }
  const size = mapBig ? 13 : 9;
  mg.font = `600 ${size}px ui-monospace, Menlo, monospace`;
  mg.textAlign = 'center';
  mg.textBaseline = 'middle';
  mg.fillStyle = '#eaf4ff';
  for (const r of f.rooms) {            // a name is drawn only where it fits inside its room
    const q = r.rects.reduce((a, b) => ((b[1] - b[0]) * (b[3] - b[2]) > (a[1] - a[0]) * (a[3] - a[2]) ? b : a));
    const name = roomName(r);
    for (const sz of [size, size - 2, size - 3]) {      // smaller lettering before leaving a name out
      mg.font = `600 ${sz}px ui-monospace, Menlo, monospace`;
      if (mg.measureText(name).width < (q[1] - q[0]) * k - 2 && sz < (q[3] - q[2]) * k - 2) {
        mg.fillText(name, X((q[0] + q[1]) / 2), Y((q[2] + q[3]) / 2));
        break;
      }
    }
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
  if (!REC_TYPE || SHARED) return;
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
// ---- room list: jump to any room on any storey (the walkable spot nearest its middle, facing the middle)
(() => {
  const sel = $('roomlist');
  floors.forEach((f, lv) => f.rooms.forEach((r, k) => {
    if (!r.rects.length) return;
    sel.append(new Option(`${floors.length > 1 ? f.name + ' · ' : ''}${roomName(r)}`, `${lv}:${k}`));
  }));
  sel.onchange = () => {
    if (!sel.value) return;
    const [lv, k] = sel.value.split(':').map(Number);
    const r = floors[lv].rooms[k];
    const q = r.rects.reduce((a, b) => ((b[1] - b[0]) * (b[3] - b[2]) > (a[1] - a[0]) * (a[3] - a[2]) ? b : a));
    const cx = (q[0] + q[1]) / 2, cy = (q[2] + q[3]) / 2, z = floors[lv].z;
    let best = null;                     // spiral out from the middle to the first spot the walker may stand on
    for (let d = 0; d < 6 && !best; d += 0.2) for (let a = 0; a < 6.28 && !best; a += 0.5) {
      const x = cx + d * Math.cos(a), y = cy + d * Math.sin(a);
      if (walk.inRect(q, x, y) && !walk.blockedAt(meta, lv, x, y) && walk.groundNear(meta, x, y, z) !== null) best = [x, y];
    }
    if (!best) return;
    if (tour) stopTour();
    if (topView) toggleTop();
    Object.assign(p, { x: best[0], y: best[1], z, pitch: 0 });
    if (Math.hypot(cx - best[0], cy - best[1]) > 0.3) p.yaw = Math.atan2(-(cx - best[0]), cy - best[1]);
    sel.value = '';
    sel.blur();
  };
})();

// ---- measure: two points on any surface (a click, or G at the crosshair when walking), the distance in metres
const measure = { on: false, pts: [], line: null };
const ray = new THREE.Raycaster();
function measurePoint(ndc) {
  ray.setFromCamera(ndc, camera);
  const hit = ray.intersectObjects(scene.children, true).find((h) => h.object.isMesh && h.object.visible);
  if (!hit) return;
  measure.pts.push(hit.point.clone());
  if (measure.pts.length === 1) { $('measure').textContent = 'Now the second point'; return; }
  const [a, b] = measure.pts;
  if (measure.line) scene.remove(measure.line);
  measure.line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]),
    new THREE.LineBasicMaterial({ color: 0xffb347, depthTest: false }));
  measure.line.renderOrder = 10;
  scene.add(measure.line);
  $('measure').textContent = `${a.distanceTo(b).toFixed(2)} m  (horizontal ${Math.hypot(a.x - b.x, a.z - b.z).toFixed(2)} m)`;
  measure.pts = [];
}
$('measurebtn').onclick = () => {
  measure.on = !measure.on;
  measure.pts = [];
  $('measurebtn').textContent = measure.on ? 'Stop measuring' : 'Measure';
  $('measure').style.display = measure.on ? 'block' : 'none';
  $('measure').textContent = 'Click the first point';
  if (!measure.on && measure.line) { scene.remove(measure.line); measure.line = null; }
};
canvas.addEventListener('pointerdown', (e) => {
  if (!measure.on || document.pointerLockElement) return;
  const r = canvas.getBoundingClientRect();
  measurePoint(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1));
});
addEventListener('keydown', (e) => { if (e.code === 'KeyG' && measure.on && !e.repeat) measurePoint(new THREE.Vector2(0, 0)); });
window.__measure = (ax, ay, bx, by) => {      // tests: measure between two screen points (NDC)
  if (!measure.on) $('measurebtn').click();
  measurePoint(new THREE.Vector2(ax, ay)); measurePoint(new THREE.Vector2(bx, by));
  return $('measure').textContent;
};
$('status').textContent = matchMedia('(pointer: coarse)').matches ? 'Tap to start' : 'Click to walk in';
// ?pose=x,y,level,yawDeg,pitchDeg (metres) and ?top=level : fixed views for previews / tests
const q = new URLSearchParams(location.search);
if (q.get('pose')) {
  const [x, y, lv, yaw, pitch] = q.get('pose').split(',').map(Number);
  Object.assign(p, { x, y, z: floors[lv || 0].z, yaw: (yaw || 0) * Math.PI / 180, pitch: (pitch || 0) * Math.PI / 180 });
  $('overlay').style.display = 'none';
}
if (q.get('top') !== null) { toggleTop(); showLevels(+q.get('top') || 0); }
if (q.get('embed') !== null || SHARED) $('newplan').remove();   // inside another site's page, or shared: no "new plan"
if (SHARED) { $('rec').remove(); $('blend').remove(); }     // a share link only views: recording and the Blender file need the owner
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
