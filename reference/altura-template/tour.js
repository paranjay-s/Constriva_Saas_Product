(() => {
  const tour = document.getElementById("tour");
  if (!tour) return;

  const sticky = tour.querySelector(".tour__sticky");
  const canvas = tour.querySelector(".tour__canvas");
  const ctx = canvas.getContext("2d", { alpha: false });
  const beats = [...tour.querySelectorAll(".beat")];
  const progressBar = tour.querySelector(".tour__progress");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");

  const ROOMS = 7; // camera moves between 8 rooms
  const TOTAL = Number(tour.dataset.frames); // frames in the sequence, first and last included
  const PER_ROOM = (TOTAL - 1) / ROOMS;

  const clamp = (v, min, max) => Math.min(Math.max(v, min), max);
  const smooth = (a, b, x) => {
    const t = clamp((x - a) / (b - a), 0, 1);
    return t * t * (3 - 2 * t);
  };

  // Phones get a portrait crop of the same frames.
  const portrait = () => innerWidth < 700 || innerHeight > innerWidth * 1.15;
  let set = portrait() ? "m" : "d";
  const SIZE = { d: [1600, 900], m: [640, 1080] }; // pixel size of each frame set
  const VERSION = tour.dataset.version || "1"; // bump when the frames are regenerated
  const src = (i) => `assets/tour/${set}/${String(i + 1).padStart(4, "0")}.webp?v=${VERSION}`;

  // ---------- Frame loading: coarse first, then fill the gaps ----------
  let frames = new Array(TOTAL);
  let queue = [];
  let active = 0;
  let generation = 0;

  const buildQueue = () => {
    const seen = new Set();
    queue = [];
    for (const stride of [24, 8, 4, 2, 1]) {
      for (let i = 0; i < TOTAL; i += stride) {
        if (!seen.has(i)) { seen.add(i); queue.push(i); }
      }
    }
    if (!seen.has(TOTAL - 1)) queue.splice(1, 0, TOTAL - 1);
  };

  const pump = () => {
    const gen = generation;
    while (active < 6 && queue.length) {
      const i = queue.shift();
      if (frames[i]) continue;
      active++;
      const img = new Image();
      img.decoding = "async";
      img.onload = () => {
        active--;
        if (gen !== generation) return;
        frames[i] = img;
        if (Math.abs(i - wanted()) < 2) needsDraw = true;
        if (!tour.classList.contains("is-live") && i === 0) { tour.classList.add("is-live"); needsDraw = true; }
        pump();
      };
      img.onerror = () => { active--; pump(); };
      img.src = src(i);
    }
  };

  const startLoading = () => {
    generation++;
    dropBitmaps();
    frames = new Array(TOTAL);
    active = 0;
    buildQueue();
    pump();
  };

  // ---------- Decoded frames near the camera ----------
  // Drawing a frame that is not decoded yet blocks the page for a few
  // milliseconds, which shows up as a stutter. Frames around the current
  // position are decoded ahead of time, off the main thread, and the rest let go.
  const AHEAD = 8; // about a fifth of a second of travel at full speed
  const BEHIND = 4;
  const bitmaps = new Map();
  const decoding = new Set();
  const canBitmap = typeof createImageBitmap === "function";

  const dropBitmaps = () => {
    for (const b of bitmaps.values()) b.close?.();
    bitmaps.clear();
    decoding.clear();
  };

  const warm = (f, dir) => {
    if (!canBitmap) return;
    const gen = generation;
    const lo = Math.max(0, Math.floor(f) - (dir < 0 ? AHEAD : BEHIND));
    const hi = Math.min(TOTAL - 1, Math.ceil(f) + (dir > 0 ? AHEAD : BEHIND));
    const keep = (i) => i >= lo - 2 && i <= hi + 2;
    for (let i = lo; i <= hi; i++) {
      if (bitmaps.has(i) || decoding.has(i) || !frames[i]) continue;
      decoding.add(i);
      createImageBitmap(frames[i]).then((b) => {
        decoding.delete(i);
        if (gen !== generation) { b.close?.(); return; }
        bitmaps.set(i, b);
      }, () => decoding.delete(i));
    }
    for (const [i, b] of bitmaps) {
      if (!keep(i)) { b.close?.(); bitmaps.delete(i); }
    }
  };

  const pic = (i) => bitmaps.get(i) || frames[i];

  // ---------- Canvas ----------
  // The canvas never holds more pixels than the frames have: extra
  // resolution only costs fill time on high-density screens.
  let cw = 0;
  let ch = 0;
  const resize = () => {
    const next = portrait() ? "m" : "d";
    if (next !== set) { set = next; startLoading(); }
    const [iw, ih] = SIZE[set];
    const w = sticky.clientWidth;
    const h = sticky.clientHeight;
    const detail = Math.max(1, 1 / Math.max(w / iw, h / ih));
    const dpr = Math.min(devicePixelRatio || 1, 2, detail);
    cw = Math.round(w * dpr);
    ch = Math.round(h * dpr);
    canvas.width = cw;
    canvas.height = ch;
    drawnKey = "";
    needsDraw = true;
  };

  const nearestLoaded = (i) => {
    if (frames[i]) return i;
    for (let d = 1; d < TOTAL; d++) {
      if (frames[i - d]) return i - d;
      if (frames[i + d]) return i + d;
    }
    return -1;
  };

  const blit = (img) => {
    const iw = img.naturalWidth || img.width;
    const ih = img.naturalHeight || img.height;
    const s = Math.max(cw / iw, ch / ih);
    const w = iw * s;
    const h = ih * s;
    ctx.drawImage(img, (cw - w) / 2, (ch - h) / 2, w, h);
  };

  // f is a fractional frame position: the two frames around it are blended,
  // so the move reads as continuous motion instead of stepping frame to frame.
  let drawnKey = "";
  const draw = (f) => {
    const a = Math.floor(f);
    const b = Math.min(a + 1, TOTAL - 1);
    let mix = f - a;
    let first = a;
    if (!frames[a] || (mix > 0.02 && !frames[b])) {
      first = nearestLoaded(Math.round(f));
      mix = 0;
    }
    if (first < 0) return;
    if (mix < 0.02) mix = 0;
    else if (mix > 0.98) { first = b; mix = 0; }
    const key = mix ? `${first}:${b}:${Math.round(mix * 32)}` : `${first}`;
    if (key === drawnKey) return;
    ctx.globalAlpha = 1;
    blit(pic(first));
    if (mix) {
      ctx.globalAlpha = mix;
      blit(pic(b));
      ctx.globalAlpha = 1;
    }
    drawnKey = key;
  };

  // ---------- Scroll timeline ----------
  // Raw room position 0..7 from scroll; the camera eases into each room so the title has time to read.
  const roomFromScroll = () => {
    const r = tour.getBoundingClientRect();
    const run = r.height - sticky.clientHeight;
    return clamp(-r.top / run, 0, 1) * ROOMS;
  };

  const ease = (t) => {
    const k = Math.floor(clamp(t, 0, ROOMS - 1e-6));
    const u = t - k;
    return k + u - (Math.sin(2 * Math.PI * u) / (2 * Math.PI)) * 0.85;
  };

  let target = roomFromScroll();
  let current = target;
  let needsDraw = true;

  const frameAt = () => {
    const t = reduced.matches ? Math.round(current) : ease(current);
    return clamp(t * PER_ROOM, 0, TOTAL - 1);
  };
  const wanted = () => Math.round(frameAt());

  const SHADE = {
    "beat--intro": ["50%", "50%"],
    "beat--left": ["22%", "38%"],
    "beat--right": ["78%", "40%"],
    "beat--low-left": ["22%", "76%"],
    "beat--low-right": ["78%", "76%"],
    "beat--end": ["50%", "52%"],
  };

  const updateBeats = (t) => {
    let top = null;
    let topO = 0;
    for (const beat of beats) {
      const at = Number(beat.dataset.at);
      let d = Math.abs(t - at);
      if (at === 0 && t < 0) d = 0;
      if (at === ROOMS && t > ROOMS) d = 0;
      const o = reduced.matches ? (d < 0.5 ? 1 : 0) : 1 - smooth(0.16, 0.42, d);
      const dir = t < at ? 1 : -1;
      beat.style.setProperty("--o", o.toFixed(3));
      beat.style.setProperty("--b", reduced.matches ? "0px" : `${((1 - o) * 12).toFixed(2)}px`);
      beat.style.setProperty("--y", reduced.matches ? "0px" : `${(dir * (1 - o) * 16).toFixed(1)}px`);
      beat.classList.toggle("is-on", o > 0.6);
      if (o > topO) { topO = o; top = beat; }
    }
    if (top) {
      const kind = Object.keys(SHADE).find((c) => top.classList.contains(c));
      const [x, y] = SHADE[kind] || SHADE["beat--intro"];
      sticky.style.setProperty("--shade-x", x);
      sticky.style.setProperty("--shade-y", y);
    }
  };

  // The camera follows the scroll position with a short, frame-rate
  // independent lag that smooths uneven wheel and touch input.
  const LAG_MS = 55;
  let raf = 0;
  let last = 0;
  let lastF = 0;
  const tick = (now) => {
    raf = 0;
    const dt = Math.min(now - (last || now - 16), 64);
    last = now;
    const diff = target - current;
    current = reduced.matches || Math.abs(diff) < 0.0008 ? target : current + diff * (1 - Math.exp(-dt / LAG_MS));
    const f = frameAt();
    warm(f, Math.sign(f - lastF) || 1);
    lastF = f;
    if (needsDraw) drawnKey = "";
    draw(f);
    updateBeats(current);
    progressBar.style.setProperty("--p", (current / ROOMS).toFixed(4));
    if (current !== target) schedule();
    else { last = 0; if (needsDraw) { needsDraw = false; schedule(); } }
  };

  const schedule = () => { if (!raf) raf = requestAnimationFrame(tick); };

  addEventListener("scroll", () => { target = roomFromScroll(); schedule(); }, { passive: true });
  addEventListener("resize", () => { resize(); target = roomFromScroll(); schedule(); });
  reduced.addEventListener?.("change", () => { needsDraw = true; schedule(); });

  // Keyboard users tabbing to a hidden beat's link get scrolled to that room.
  tour.addEventListener("focusin", (e) => {
    const beat = e.target.closest(".beat");
    if (!beat) return;
    const r = tour.getBoundingClientRect();
    const run = r.height - sticky.clientHeight;
    const y = scrollY + r.top + (Number(beat.dataset.at) / ROOMS) * run;
    scrollTo({ top: y, behavior: reduced.matches ? "auto" : "smooth" });
  });

  resize();
  const io = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting)) { io.disconnect(); startLoading(); }
  }, { rootMargin: "150% 0px" });
  io.observe(tour);
  schedule();
})();
