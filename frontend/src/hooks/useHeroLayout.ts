import { useEffect, type RefObject } from "react";
import { clamp } from "../lib/math";

const ASPECT = 1200 / 1000;
const ROOF_Y = 0.455; // top edge of the roof slab
const HOUSE_CX = 0.49; // horizontal centre of the house
const CLIP_Y = 0.476; // just below the lowest roof edge; hides letter slivers in the side gaps

interface FontMetrics {
  ascent: number;
  xHeight: number;
}

export function useHeroLayout(heroRef: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const hero = heroRef.current;
    if (!hero) return;

    const root = document.documentElement;
    root.classList.add("js");

    const wordmark = hero.querySelector<HTMLElement>(".wordmark");
    const line = wordmark?.querySelector<HTMLElement>(".wordmark__line");
    const nav = hero.querySelector<HTMLElement>(".nav");
    const images = Array.from(hero.querySelectorAll<HTMLImageElement>(".stage__img"));

    if (!wordmark || !line || !nav) return;

    let metrics: FontMetrics | null = null;

    const measure = (): FontMetrics => {
      const style = getComputedStyle(wordmark);
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      if (!ctx) return { ascent: 0.72, xHeight: 0.5 };
      ctx.font = `${style.fontWeight} 100px ${style.fontFamily}`;
      const ascent = ctx.measureText("l").actualBoundingBoxAscent / 100;
      const xHeight = ctx.measureText("x").actualBoundingBoxAscent / 100;
      return { ascent, xHeight };
    };

    const layout = () => {
      const W = hero.clientWidth;
      const H = hero.clientHeight;
      if (!W || !H) return;
      const mobile = W < 700;

      // Cover the hero with the photo, keeping the roof line near mid-height.
      const sw = Math.max(W, H * ASPECT);
      const sh = sw / ASPECT;
      const roofTarget = H * (mobile ? 0.53 : 0.44);
      const sy = clamp(roofTarget - ROOF_Y * sh, H - sh, 0);
      const sx = clamp(W / 2 - HOUSE_CX * sw, W - sw, 0);
      const roof = sy + ROOF_Y * sh;

      hero.style.setProperty("--sw", `${sw}px`);
      hero.style.setProperty("--sh", `${sh}px`);
      hero.style.setProperty("--sx", `${sx}px`);
      hero.style.setProperty("--sy", `${sy}px`);

      if (!metrics) metrics = measure();

      // Size the wordmark to the width first, then cap it so the tallest
      // letters stay clear of the navigation.
      const sideMargin = W * (mobile ? 0.035 : 0.06);
      const targetWidth = W - sideMargin * 2;
      wordmark.style.setProperty("--wm-size", "100px");
      const widthAt100 = line.getBoundingClientRect().width;
      let size = widthAt100 ? (targetWidth / widthAt100) * 100 : 100;

      const hidden = mobile ? 0.14 : 0.2; // share of the x-height tucked behind the roof
      const navBottom = nav.getBoundingClientRect().bottom - hero.getBoundingClientRect().top;
      const minTop = navBottom + H * (mobile ? 0.12 : 0.07);
      const maxSize = (roof - minTop) / (metrics.ascent - hidden * metrics.xHeight);
      size = Math.min(size, maxSize);

      // The short letters must also start below the collections index (top right).
      const index = hero.querySelector<HTMLElement>(".index");
      if (index && index.offsetParent) {
        const indexBottom = index.offsetTop + index.offsetHeight + H * 0.025;
        size = Math.min(size, (roof - indexBottom) / ((1 - hidden) * metrics.xHeight));
      }

      const baseline = roof + hidden * metrics.xHeight * size;
      wordmark.style.setProperty("--wm-size", `${size}px`);

      const box = wordmark.getBoundingClientRect();
      const lineRect = line.getBoundingClientRect();
      const probe = document.createElement("span");
      probe.style.cssText = "display:inline-block;width:0;height:0;vertical-align:baseline";
      line.appendChild(probe);
      const baselineInBox = probe.getBoundingClientRect().top - box.top;
      probe.remove();

      const wmWidth = lineRect.width;
      const wmX = (W - wmWidth) / 2;
      const wmY = baseline - baselineInBox;
      wordmark.style.setProperty("--wm-x", `${wmX}px`);
      wordmark.style.setProperty("--wm-y", `${wmY}px`);
      const clipInBox = sy + CLIP_Y * sh - wmY;
      wordmark.style.clipPath = `polygon(-10% -30%, 110% -30%, 110% ${clipInBox}px, -10% ${clipInBox}px)`;
    };

    const ready = () => root.classList.add("is-ready");

    const decode = (img: HTMLImageElement) =>
      img.complete && img.naturalWidth
        ? Promise.resolve()
        : img.decode().catch(() => {});

    let cancelled = false;

    const fonts =
      "fonts" in document
        ? document.fonts.load('500 100px "Poppins"').catch(() => {})
        : Promise.resolve();
    const fontTimeout = new Promise((r) => setTimeout(r, 1500));

    Promise.race([fonts, fontTimeout])
      .then(() => {
        if (cancelled) return;
        metrics = null;
        layout();
        return Promise.all(images.map(decode));
      })
      .then(() => {
        if (cancelled) return;
        requestAnimationFrame(() => {
          if (cancelled) return;
          requestAnimationFrame(ready);
        });
      });

    if ("fonts" in document) {
      document.fonts.ready.then(() => {
        if (cancelled) return;
        metrics = null;
        layout();
      });
    }

    let raf = 0;
    const onResize = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        if (!cancelled) layout();
      });
    };

    window.addEventListener("resize", onResize);
    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(onResize);
      observer.observe(hero);
    }

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      observer?.disconnect();
    };
  }, [heroRef]);
}

