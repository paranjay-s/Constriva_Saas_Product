import { useEffect, type RefObject } from "react";
import { clamp, smooth } from "../lib/math";
import { FRAME_COUNT, VERSION, ROOMS, PER_ROOM } from "../content/tour.config";

const SIZE: Record<string, [number, number]> = {
  d: [1600, 900],
  m: [640, 1080],
};

const SHADE: Record<string, [string, string]> = {
  "beat--intro": ["50%", "50%"],
  "beat--left": ["22%", "38%"],
  "beat--right": ["78%", "40%"],
  "beat--low-left": ["22%", "76%"],
  "beat--low-right": ["78%", "76%"],
  "beat--end": ["50%", "52%"],
};

const AHEAD = 8;
const BEHIND = 4;
const LAG_MS = 55;

export function useTourScrub(tourRef: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const tour = tourRef.current;
    if (!tour) return;

    const sticky = tour.querySelector<HTMLElement>(".tour__sticky");
    const canvas = tour.querySelector<HTMLCanvasElement>(".tour__canvas");
    const progressBar = tour.querySelector<HTMLElement>(".tour__progress");
    const beats = Array.from(tour.querySelectorAll<HTMLElement>(".beat"));

    if (!sticky || !canvas || !progressBar) return;

    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    const reducedQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

    const portrait = () =>
      window.innerWidth < 700 || window.innerHeight > window.innerWidth * 1.15;
    let set = portrait() ? "m" : "d";

    const getBaseUrl = () => {
      const base = import.meta.env.BASE_URL || "/";
      return base.endsWith("/") ? base : `${base}/`;
    };

    const src = (i: number) =>
      `${getBaseUrl()}assets/tour/${set}/${String(i + 1).padStart(4, "0")}.webp?v=${VERSION}`;

    // Frame loading state
    let frames: (HTMLImageElement | undefined)[] = new Array(FRAME_COUNT);
    let queue: number[] = [];
    let active = 0;
    let generation = 0;
    let cancelled = false;

    const buildQueue = () => {
      const seen = new Set<number>();
      queue = [];
      for (const stride of [24, 8, 4, 2, 1]) {
        for (let i = 0; i < FRAME_COUNT; i += stride) {
          if (!seen.has(i)) {
            seen.add(i);
            queue.push(i);
          }
        }
      }
      if (!seen.has(FRAME_COUNT - 1)) queue.splice(1, 0, FRAME_COUNT - 1);
    };

    const pump = () => {
      if (cancelled) return;
      const gen = generation;
      while (active < 6 && queue.length) {
        const i = queue.shift()!;
        if (frames[i]) continue;
        active++;
        const img = new Image();
        img.decoding = "async";
        img.onload = () => {
          active--;
          if (cancelled || gen !== generation) return;
          frames[i] = img;
          if (Math.abs(i - wanted()) < 2) needsDraw = true;
          if (!tour.classList.contains("is-live") && i === 0) {
            tour.classList.add("is-live");
            needsDraw = true;
          }
          pump();
        };
        img.onerror = () => {
          active--;
          if (!cancelled) pump();
        };
        img.src = src(i);
      }
    };

    const dropBitmaps = () => {
      for (const b of bitmaps.values()) {
        if ("close" in b && typeof b.close === "function") b.close();
      }
      bitmaps.clear();
      decoding.clear();
    };

    const startLoading = () => {
      generation++;
      dropBitmaps();
      frames = new Array(FRAME_COUNT);
      active = 0;
      buildQueue();
      pump();
    };

    // Decoded bitmap cache
    const bitmaps = new Map<number, ImageBitmap>();
    const decoding = new Set<number>();
    const canBitmap = typeof createImageBitmap === "function";

    const warm = (f: number, dir: number) => {
      if (!canBitmap || cancelled) return;
      const gen = generation;
      const lo = Math.max(0, Math.floor(f) - (dir < 0 ? AHEAD : BEHIND));
      const hi = Math.min(FRAME_COUNT - 1, Math.ceil(f) + (dir > 0 ? AHEAD : BEHIND));
      const keep = (i: number) => i >= lo - 2 && i <= hi + 2;

      for (let i = lo; i <= hi; i++) {
        if (bitmaps.has(i) || decoding.has(i) || !frames[i]) continue;
        decoding.add(i);
        createImageBitmap(frames[i]!).then(
          (b) => {
            decoding.delete(i);
            if (cancelled || gen !== generation) {
              if ("close" in b && typeof b.close === "function") b.close();
              return;
            }
            bitmaps.set(i, b);
          },
          () => decoding.delete(i)
        );
      }

      for (const [i, b] of bitmaps) {
        if (!keep(i)) {
          if ("close" in b && typeof b.close === "function") b.close();
          bitmaps.delete(i);
        }
      }
    };

    const pic = (i: number): HTMLImageElement | ImageBitmap | undefined =>
      bitmaps.get(i) || frames[i];

    // Canvas sizing & blit
    let cw = 0;
    let ch = 0;
    let drawnKey = "";
    let needsDraw = true;

    const resize = () => {
      const next = portrait() ? "m" : "d";
      if (next !== set) {
        set = next;
        startLoading();
      }
      const [iw, ih] = SIZE[set];
      const w = sticky.clientWidth;
      const h = sticky.clientHeight;
      if (!w || !h) return;
      const detail = Math.max(1, 1 / Math.max(w / iw, h / ih));
      const dpr = Math.min(window.devicePixelRatio || 1, 2, detail);
      cw = Math.round(w * dpr);
      ch = Math.round(h * dpr);
      canvas.width = cw;
      canvas.height = ch;
      drawnKey = "";
      needsDraw = true;
    };

    const nearestLoaded = (i: number): number => {
      if (frames[i]) return i;
      for (let d = 1; d < FRAME_COUNT; d++) {
        if (frames[i - d]) return i - d;
        if (frames[i + d]) return i + d;
      }
      return -1;
    };

    const blit = (img: HTMLImageElement | ImageBitmap) => {
      const iw = "naturalWidth" in img ? img.naturalWidth : img.width;
      const ih = "naturalHeight" in img ? img.naturalHeight : img.height;
      if (!iw || !ih) return;
      const s = Math.max(cw / iw, ch / ih);
      const w = iw * s;
      const h = ih * s;
      ctx.drawImage(img, (cw - w) / 2, (ch - h) / 2, w, h);
    };

    const draw = (f: number) => {
      const a = Math.floor(f);
      const b = Math.min(a + 1, FRAME_COUNT - 1);
      let mix = f - a;
      let first = a;

      if (!frames[a] || (mix > 0.02 && !frames[b])) {
        first = nearestLoaded(Math.round(f));
        mix = 0;
      }
      if (first < 0) return;
      if (mix < 0.02) mix = 0;
      else if (mix > 0.98) {
        first = b;
        mix = 0;
      }

      const key = mix ? `${first}:${b}:${Math.round(mix * 32)}` : `${first}`;
      if (key === drawnKey) return;

      const imgA = pic(first);
      if (!imgA) return;

      ctx.globalAlpha = 1;
      blit(imgA);
      if (mix) {
        const imgB = pic(b);
        if (imgB) {
          ctx.globalAlpha = mix;
          blit(imgB);
          ctx.globalAlpha = 1;
        }
      }
      drawnKey = key;
    };

    // Scroll timeline
    const roomFromScroll = (): number => {
      const r = tour.getBoundingClientRect();
      const run = r.height - sticky.clientHeight;
      if (run <= 0) return 0;
      return clamp(-r.top / run, 0, 1) * ROOMS;
    };

    const ease = (t: number): number => {
      const k = Math.floor(clamp(t, 0, ROOMS - 1e-6));
      const u = t - k;
      return k + u - (Math.sin(2 * Math.PI * u) / (2 * Math.PI)) * 0.85;
    };

    let target = roomFromScroll();
    let current = target;

    const frameAt = () => {
      const t = reducedQuery.matches ? Math.round(current) : ease(current);
      return clamp(t * PER_ROOM, 0, FRAME_COUNT - 1);
    };
    const wanted = () => Math.round(frameAt());

    const updateBeats = (t: number) => {
      let top: HTMLElement | null = null;
      let topO = 0;

      for (const beat of beats) {
        const at = Number(beat.dataset.at);
        let d = Math.abs(t - at);
        if (at === 0 && t < 0) d = 0;
        if (at === ROOMS && t > ROOMS) d = 0;
        const o = reducedQuery.matches ? (d < 0.5 ? 1 : 0) : 1 - smooth(0.16, 0.42, d);
        const dir = t < at ? 1 : -1;
        beat.style.setProperty("--o", o.toFixed(3));
        beat.style.setProperty(
          "--b",
          reducedQuery.matches ? "0px" : `${((1 - o) * 12).toFixed(2)}px`
        );
        beat.style.setProperty(
          "--y",
          reducedQuery.matches ? "0px" : `${(dir * (1 - o) * 16).toFixed(1)}px`
        );
        beat.classList.toggle("is-on", o > 0.6);
        if (o > topO) {
          topO = o;
          top = beat;
        }
      }

      if (top) {
        const kind = Object.keys(SHADE).find((c) => top!.classList.contains(c));
        const [x, y] = SHADE[kind || ""] || SHADE["beat--intro"];
        sticky.style.setProperty("--shade-x", x);
        sticky.style.setProperty("--shade-y", y);
      }
    };

    let raf = 0;
    let last = 0;
    let lastF = 0;

    const tick = (now: number) => {
      raf = 0;
      if (cancelled) return;
      const dt = Math.min(now - (last || now - 16), 64);
      last = now;
      const diff = target - current;
      current =
        reducedQuery.matches || Math.abs(diff) < 0.0008
          ? target
          : current + diff * (1 - Math.exp(-dt / LAG_MS));

      const f = frameAt();
      warm(f, Math.sign(f - lastF) || 1);
      lastF = f;
      if (needsDraw) drawnKey = "";
      draw(f);
      updateBeats(current);
      progressBar.style.setProperty("--p", (current / ROOMS).toFixed(4));

      if (current !== target) {
        schedule();
      } else {
        last = 0;
        if (needsDraw) {
          needsDraw = false;
          schedule();
        }
      }
    };

    const schedule = () => {
      if (!raf && !cancelled) raf = requestAnimationFrame(tick);
    };

    const handleScroll = () => {
      target = roomFromScroll();
      schedule();
    };

    const handleResize = () => {
      resize();
      target = roomFromScroll();
      schedule();
    };

    const handleReducedChange = () => {
      needsDraw = true;
      schedule();
    };

    const handleFocusIn = (e: FocusEvent) => {
      const beat = (e.target as HTMLElement)?.closest<HTMLElement>(".beat");
      if (!beat) return;
      const r = tour.getBoundingClientRect();
      const run = r.height - sticky.clientHeight;
      const y = window.scrollY + r.top + (Number(beat.dataset.at) / ROOMS) * run;
      window.scrollTo({
        top: y,
        behavior: reducedQuery.matches ? "auto" : "smooth",
      });
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    window.addEventListener("resize", handleResize);
    tour.addEventListener("focusin", handleFocusIn);
    if (reducedQuery.addEventListener) {
      reducedQuery.addEventListener("change", handleReducedChange);
    } else {
      reducedQuery.addListener(handleReducedChange);
    }

    resize();

    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          io.disconnect();
          startLoading();
        }
      },
      { rootMargin: "150% 0px" }
    );
    io.observe(tour);
    schedule();

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", handleScroll);
      window.removeEventListener("resize", handleResize);
      tour.removeEventListener("focusin", handleFocusIn);
      if (reducedQuery.removeEventListener) {
        reducedQuery.removeEventListener("change", handleReducedChange);
      } else {
        reducedQuery.removeListener(handleReducedChange);
      }
      io.disconnect();
      dropBitmaps();
    };
  }, [tourRef]);
}
