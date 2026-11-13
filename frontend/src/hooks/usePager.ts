import { useEffect, type RefObject } from "react";
import { ROOMS } from "../content/tour.config";

interface GlideState {
  from: number;
  to: number;
  v: number;
  start: number;
  ms: number;
}

const HERO_MS = 1000;
const ROOM_MS = 4500;
const AHEAD = 1;

export function usePager(
  tourRef: RefObject<HTMLElement | null>,
  heroRef: RefObject<HTMLElement | null>
) {
  useEffect(() => {
    const tour = tourRef.current;
    if (!tour) return;
    const sticky = tour.querySelector<HTMLElement>(".tour__sticky");
    if (!sticky) return;

    const hero = heroRef.current;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");

    const menuOpen = () => hero?.classList.contains("is-menu-open");
    const maxScroll = () =>
      document.documentElement.scrollHeight - window.innerHeight;

    let cache: number[] | null = null;
    const stops = (): number[] => {
      if (cache) return cache;
      const top = tour.getBoundingClientRect().top + window.scrollY;
      const run = tour.offsetHeight - sticky.clientHeight;
      const list = [0];
      for (let k = 0; k <= ROOMS; k++) {
        list.push(
          Math.min(Math.round(top + (k / ROOMS) * run), maxScroll())
        );
      }
      cache = list;
      return list;
    };

    const nearest = (y: number = window.scrollY): number => {
      const list = stops();
      let best = 0;
      for (let i = 1; i < list.length; i++) {
        if (Math.abs(list[i] - y) < Math.abs(list[best] - y)) best = i;
      }
      return best;
    };

    let g: GlideState | null = null;
    let anim = 0;
    let index = nearest();

    const at = (now: number) => {
      if (!g) return { u: 1, pos: window.scrollY, vel: 0 };
      const u = Math.min((now - g.start) / g.ms, 1);
      const u2 = u * u;
      const u3 = u2 * u;
      const pos =
        (2 * u3 - 3 * u2 + 1) * g.from +
        (u3 - 2 * u2 + u) * g.v * g.ms +
        (3 * u2 - 2 * u3) * g.to;
      const vel =
        ((6 * u2 - 6 * u) * g.from +
          (3 * u2 - 4 * u + 1) * g.v * g.ms +
          (6 * u - 6 * u2) * g.to) /
        g.ms;
      return { u, pos, vel };
    };

    const step = (now: number) => {
      const s = at(now);
      window.scrollTo(0, Math.round(s.pos * 2) / 2);
      if (s.u < 1) {
        anim = requestAnimationFrame(step);
      } else {
        anim = 0;
        g = null;
      }
    };

    const glideTo = (i: number) => {
      const list = stops();
      index = Math.max(0, Math.min(list.length - 1, i));
      const to = list[index];
      const now = performance.now();
      let from = window.scrollY;
      let v = 0;
      if (g) {
        const s = at(now);
        from = s.pos;
        v = s.vel;
      }
      cancelAnimationFrame(anim);
      anim = 0;
      g = null;

      if (reduced.matches || Math.abs(to - from) < 2) {
        window.scrollTo(0, to);
        return;
      }

      const heroLeg = index === 0 || (index === 1 && from < list[1]);
      const gap = Math.max(1, (list[list.length - 1] - list[1]) / ROOMS);
      const dist = Math.abs(to - from) / (heroLeg ? Math.max(1, list[1]) : gap);
      const ms = (heroLeg ? HERO_MS : ROOM_MS) * Math.pow(Math.max(dist, 0.35), 0.8);

      const dir = Math.sign(to - from);
      if (v * dir > 0) {
        v = dir * Math.min(Math.abs(v), (2 * Math.abs(to - from)) / ms);
      }

      g = { from, to, v, start: now, ms };
      anim = requestAnimationFrame(step);
    };

    const go = (dir: number) => {
      if (menuOpen()) return;
      if (!g && Math.abs(stops()[index] - window.scrollY) > 4) {
        index = nearest();
      }
      const next = index + dir;
      if (g) {
        const here = nearest(at(performance.now()).pos);
        if (Math.abs(next - here) > AHEAD + 1) return;
      }
      if (next < 0 || next >= stops().length) return;
      glideTo(next);
    };

    // Wheel listener
    let lastWheel = 0;
    let lastAbs = 0;
    let armed = true;

    const handleWheel = (e: WheelEvent) => {
      if (e.ctrlKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
      if (menuOpen()) return;
      e.preventDefault();

      const now = performance.now();
      const dy =
        e.deltaMode === 1
          ? e.deltaY * 16
          : e.deltaMode === 2
          ? e.deltaY * window.innerHeight
          : e.deltaY;
      const abs = Math.abs(dy);
      const quiet = now - lastWheel > 180;
      const stronger = abs > lastAbs * 1.8 && abs > 24;
      lastWheel = now;
      lastAbs = abs;

      if (quiet || stronger) armed = true;
      if (!armed || abs < 4) return;
      armed = false;
      go(Math.sign(dy));
    };

    // Touch listener
    let touchY: number | null = null;
    let touchT = 0;
    let fired = false;

    const handleTouchStart = (e: TouchEvent) => {
      if (e.touches.length !== 1) {
        touchY = null;
        return;
      }
      touchY = e.touches[0].clientY;
      touchT = performance.now();
      fired = false;
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (touchY === null || e.touches.length !== 1 || menuOpen()) return;
      e.preventDefault();
      const dy = touchY - e.touches[0].clientY;
      if (!fired && Math.abs(dy) > 28) {
        fired = true;
        go(Math.sign(dy));
      }
    };

    const handleTouchEnd = (e: TouchEvent) => {
      if (touchY === null) return;
      const dy = touchY - e.changedTouches[0].clientY;
      const fast = performance.now() - touchT < 300;
      touchY = null;
      if (!fired && Math.abs(dy) > (fast ? 16 : 28)) {
        go(Math.sign(dy));
      }
    };

    const handleTouchCancel = () => {
      touchY = null;
    };

    // Keyboard listener
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      const target = e.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable]")) return;

      const map: Record<string, number> = {
        ArrowDown: 1,
        PageDown: 1,
        ArrowUp: -1,
        PageUp: -1,
        " ": e.shiftKey ? -1 : 1,
      };

      if (e.key === "Home" || e.key === "End") {
        e.preventDefault();
        glideTo(e.key === "Home" ? 0 : stops().length - 1);
        return;
      }

      if (!(e.key in map)) return;
      if (e.key === " " && target?.closest("a, button")) return;

      e.preventDefault();
      if (e.repeat && g) return;
      go(map[e.key]);
    };

    // Settle timeout
    let settle = 0;
    const handleScroll = () => {
      if (anim) return;
      clearTimeout(settle);
      settle = window.setTimeout(() => {
        if (anim || touchY !== null) return;
        const i = nearest();
        if (Math.abs(stops()[i] - window.scrollY) > 4) glideTo(i);
        else index = i;
      }, 260);
    };

    const handleResize = () => {
      cache = null;
      if (anim) glideTo(index);
      else window.scrollTo(0, stops()[index]);
    };

    window.addEventListener("wheel", handleWheel, { passive: false });
    window.addEventListener("touchstart", handleTouchStart, { passive: true });
    window.addEventListener("touchmove", handleTouchMove, { passive: false });
    window.addEventListener("touchend", handleTouchEnd, { passive: true });
    window.addEventListener("touchcancel", handleTouchCancel, { passive: true });
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("scroll", handleScroll, { passive: true });
    window.addEventListener("resize", handleResize);

    let bodyObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      bodyObserver = new ResizeObserver(() => {
        cache = null;
      });
      bodyObserver.observe(document.body);
    }

    return () => {
      cancelAnimationFrame(anim);
      clearTimeout(settle);
      window.removeEventListener("wheel", handleWheel);
      window.removeEventListener("touchstart", handleTouchStart);
      window.removeEventListener("touchmove", handleTouchMove);
      window.removeEventListener("touchend", handleTouchEnd);
      window.removeEventListener("touchcancel", handleTouchCancel);
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("scroll", handleScroll);
      window.removeEventListener("resize", handleResize);
      bodyObserver?.disconnect();
    };
  }, [tourRef, heroRef]);
}
