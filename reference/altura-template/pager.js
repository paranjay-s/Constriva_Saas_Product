// One screen per scroll: a wheel turn, swipe or key press glides to the next stop.
// Stops are the hero, then each room of the walkthrough. Dragging the scrollbar
// or following a link still works; the page settles on the nearest stop after.
//
// Input is never dropped while a glide runs: a new push in the same direction
// queues the next room, a push the other way turns back, and either one picks
// up the current speed so the camera never stops dead or jumps.
(() => {
  const tour = document.getElementById("tour");
  const sticky = tour?.querySelector(".tour__sticky");
  if (!tour || !sticky) return;

  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const rooms = Math.max(...[...tour.querySelectorAll(".beat")].map((b) => Number(b.dataset.at) || 0));
  const HERO_MS = 1000;
  const ROOM_MS = 4500;
  const AHEAD = 1; // rooms that may be queued beyond the one being approached

  const hero = document.querySelector(".hero");
  const menuOpen = () => hero?.classList.contains("is-menu-open");
  const maxScroll = () => document.documentElement.scrollHeight - innerHeight;

  let cache = null;
  const stops = () => {
    if (cache) return cache;
    const top = tour.getBoundingClientRect().top + scrollY;
    const run = tour.offsetHeight - sticky.clientHeight;
    const list = [0];
    for (let k = 0; k <= rooms; k++) list.push(Math.min(Math.round(top + (k / rooms) * run), maxScroll()));
    return (cache = list);
  };

  const nearest = (y = scrollY) => {
    const list = stops();
    let best = 0;
    for (let i = 1; i < list.length; i++) if (Math.abs(list[i] - y) < Math.abs(list[best] - y)) best = i;
    return best;
  };

  // ---------- Glide ----------
  // A cubic from the current position and speed to the target, arriving at rest.
  // From rest it is a plain smoothstep; mid-glide it carries the speed it already has.
  let g = null; // { from, to, v, start, ms }
  let anim = 0;
  let index = nearest();

  const at = (now) => {
    const u = Math.min((now - g.start) / g.ms, 1);
    const u2 = u * u;
    const u3 = u2 * u;
    const pos = (2 * u3 - 3 * u2 + 1) * g.from + (u3 - 2 * u2 + u) * g.v * g.ms + (3 * u2 - 2 * u3) * g.to;
    const vel = ((6 * u2 - 6 * u) * g.from + (3 * u2 - 4 * u + 1) * g.v * g.ms + (6 * u - 6 * u2) * g.to) / g.ms;
    return { u, pos, vel };
  };

  const step = (now) => {
    const s = at(now);
    scrollTo(0, Math.round(s.pos * 2) / 2);
    if (s.u < 1) anim = requestAnimationFrame(step);
    else { anim = 0; g = null; }
  };

  const glideTo = (i) => {
    const list = stops();
    index = Math.max(0, Math.min(list.length - 1, i));
    const to = list[index];
    const now = performance.now();
    let from = scrollY;
    let v = 0;
    if (g) { const s = at(now); from = s.pos; v = s.vel; }
    cancelAnimationFrame(anim);
    anim = 0;
    g = null;
    if (reduced.matches || Math.abs(to - from) < 2) { scrollTo(0, to); return; }

    const heroLeg = index === 0 || (index === 1 && from < list[1]);
    const gap = Math.max(1, (list[list.length - 1] - list[1]) / rooms);
    const dist = Math.abs(to - from) / (heroLeg ? Math.max(1, list[1]) : gap);
    // Longer queued runs take a little less time per room, so a held scroll flows.
    let ms = (heroLeg ? HERO_MS : ROOM_MS) * Math.pow(Math.max(dist, 0.35), 0.8);
    // Carrying speed into a short distance would overshoot the room; trim it.
    const dir = Math.sign(to - from);
    if (v * dir > 0) v = dir * Math.min(Math.abs(v), (2 * Math.abs(to - from)) / ms);
    g = { from, to, v, start: now, ms };
    anim = requestAnimationFrame(step);
  };

  const go = (dir) => {
    if (menuOpen()) return;
    if (!g && Math.abs(stops()[index] - scrollY) > 4) index = nearest();
    let next = index + dir;
    if (g) {
      // Never run further than one room past where the camera is heading now.
      const here = nearest(at(performance.now()).pos);
      if (Math.abs(next - here) > AHEAD + 1) return;
    }
    if (next < 0 || next >= stops().length) return;
    glideTo(next);
  };

  // ---------- Wheel and trackpad ----------
  // One gesture moves one room. A trackpad flick keeps sending events for a
  // second or more after the fingers lift; those belong to the same gesture
  // until the stream goes quiet or a clearly stronger push starts a new one.
  let lastWheel = 0;
  let lastAbs = 0;
  let armed = true;
  addEventListener("wheel", (e) => {
    if (e.ctrlKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return; // pinch zoom, sideways
    if (menuOpen()) return;
    e.preventDefault();
    const now = performance.now();
    const dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaMode === 2 ? e.deltaY * innerHeight : e.deltaY;
    const abs = Math.abs(dy);
    const quiet = now - lastWheel > 180;
    const stronger = abs > lastAbs * 1.8 && abs > 24;
    lastWheel = now;
    lastAbs = abs;
    if (quiet || stronger) armed = true;
    if (!armed || abs < 4) return;
    armed = false;
    go(Math.sign(dy));
  }, { passive: false });

  // ---------- Touch ----------
  // The glide starts as soon as the finger has clearly moved, not when it lifts.
  let touchY = null;
  let touchT = 0;
  let fired = false;
  addEventListener("touchstart", (e) => {
    if (e.touches.length !== 1) { touchY = null; return; }
    touchY = e.touches[0].clientY;
    touchT = performance.now();
    fired = false;
  }, { passive: true });
  addEventListener("touchmove", (e) => {
    if (touchY === null || e.touches.length !== 1 || menuOpen()) return;
    e.preventDefault();
    const dy = touchY - e.touches[0].clientY;
    if (!fired && Math.abs(dy) > 28) { fired = true; go(Math.sign(dy)); }
  }, { passive: false });
  addEventListener("touchend", (e) => {
    if (touchY === null) return;
    const dy = touchY - e.changedTouches[0].clientY;
    const fast = performance.now() - touchT < 300;
    touchY = null;
    if (!fired && Math.abs(dy) > (fast ? 16 : 28)) go(Math.sign(dy));
  }, { passive: true });
  addEventListener("touchcancel", () => { touchY = null; }, { passive: true });

  // ---------- Keyboard ----------
  addEventListener("keydown", (e) => {
    if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.target.closest?.("input, textarea, select, [contenteditable]")) return;
    const map = { ArrowDown: 1, PageDown: 1, ArrowUp: -1, PageUp: -1, " ": e.shiftKey ? -1 : 1 };
    if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      glideTo(e.key === "Home" ? 0 : stops().length - 1);
      return;
    }
    if (!(e.key in map)) return;
    if (e.key === " " && e.target.closest?.("a, button")) return;
    e.preventDefault();
    if (e.repeat && g) return; // holding a key queues one room at a time
    go(map[e.key]);
  });

  // ---------- Settle after other movement ----------
  // Scrollbar drags, links and focus jumps end between stops; ease to the nearest.
  let settle = 0;
  addEventListener("scroll", () => {
    if (anim) return;
    clearTimeout(settle);
    settle = setTimeout(() => {
      if (anim || touchY !== null) return;
      const i = nearest();
      if (Math.abs(stops()[i] - scrollY) > 4) glideTo(i);
      else index = i;
    }, 260);
  }, { passive: true });

  addEventListener("resize", () => {
    cache = null;
    if (anim) glideTo(index);
    else scrollTo(0, stops()[index]);
  });
  // Fonts and the hero can change the page height after load.
  new ResizeObserver(() => { cache = null; }).observe(document.body);
})();
