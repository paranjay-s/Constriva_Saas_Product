import { useEffect, useRef, useState } from "react";
import { BrandMark } from "../../components/ui/Icons";

const FRAME_COUNT = 421;
const VERSION = "1";

const FEATURE_HIGHLIGHTS = [
  {
    title: "2D Plan to Live 3D Walkthrough",
    description: "Upload any CAD blueprint or PDF — Constriva synthesizes a continuous 3D architectural model you can explore.",
    tag: "Spatial BIM Engine",
  },
  {
    title: "Automated Material-wise BOQ",
    description: "Every brick, timber beam, slab, and fixture calculated down to the unit and exported as an official PDF schedule.",
    tag: "Cost & Quantity Engine",
  },
  {
    title: "AI Vision Material Identification",
    description: "Snap any building facade or interior finish — computer vision identifies textures, specs, and volume estimates.",
    tag: "Material Intelligence",
  },
  {
    title: "Natural Prompt to CAD Floor Plan",
    description: "Describe room dimensions and orientation in plain words — generate working 2D CAD blueprints instantly.",
    tag: "Generative Architecture",
  },
];

export function AuthCinematic() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [activeHighlightIndex, setActiveHighlightIndex] = useState(0);

  // Rotate highlight quotes every 4.5 seconds
  useEffect(() => {
    const timer = setInterval(() => {
      setActiveHighlightIndex((prev) => (prev + 1) % FEATURE_HIGHLIGHTS.length);
    }, 4500);
    return () => clearInterval(timer);
  }, []);

  // Run the cinematic walkthrough frame loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    let cancelled = false;
    let animId = 0;
    const base = import.meta.env.BASE_URL || "/";
    const baseUrl = base.endsWith("/") ? base : `${base}/`;

    const getFrameUrl = (i: number) =>
      `${baseUrl}assets/tour/d/${String(i + 1).padStart(4, "0")}.webp?v=${VERSION}`;

    // Frame cache
    const cache = new Map<number, HTMLImageElement>();

    const loadImage = (index: number): Promise<HTMLImageElement> => {
      return new Promise((resolve) => {
        if (cache.has(index)) {
          resolve(cache.get(index)!);
          return;
        }
        const img = new Image();
        img.decoding = "async";
        img.src = getFrameUrl(index);
        img.onload = () => {
          cache.set(index, img);
          resolve(img);
        };
        img.onerror = () => {
          resolve(img);
        };
      });
    };

    // Pre-cache initial frame batch
    for (let i = 0; i < 40; i++) {
      loadImage(i);
    }

    let currentFrame = 0;
    let direction = 1;
    let lastTime = performance.now();

    const resize = () => {
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(rect.width * dpr);
      canvas.height = Math.round(rect.height * dpr);
    };

    resize();
    window.addEventListener("resize", resize);

    const blit = (img: HTMLImageElement) => {
      if (!img.naturalWidth || !canvas) return;
      const cw = canvas.width;
      const ch = canvas.height;
      const iw = img.naturalWidth;
      const ih = img.naturalHeight;
      const scale = Math.max(cw / iw, ch / ih);
      const w = iw * scale;
      const h = ih * scale;
      ctx.drawImage(img, (cw - w) / 2, (ch - h) / 2, w, h);
    };

    const loop = (now: number) => {
      if (cancelled) return;

      const elapsed = now - lastTime;
      // Ambient cinematic playback rate: ~24 frames per second
      if (elapsed > 42) {
        lastTime = now;
        currentFrame += direction;

        if (currentFrame >= FRAME_COUNT - 1) {
          currentFrame = FRAME_COUNT - 1;
          direction = -1; // Smoothly reverse once reaching terrace
        } else if (currentFrame <= 0) {
          currentFrame = 0;
          direction = 1;
        }

        // Preload ahead in direction of travel
        const lookAhead = 15;
        for (let k = 1; k <= lookAhead; k++) {
          const nextIdx = currentFrame + direction * k;
          if (nextIdx >= 0 && nextIdx < FRAME_COUNT) {
            loadImage(nextIdx);
          }
        }
      }

      // Draw current frame or nearest loaded
      const targetIdx = Math.floor(currentFrame);
      let img = cache.get(targetIdx);
      if (!img || !img.complete) {
        // Find nearest loaded
        for (let d = 1; d < 30; d++) {
          const f1 = cache.get(targetIdx - d);
          if (f1 && f1.complete) {
            img = f1;
            break;
          }
          const f2 = cache.get(targetIdx + d);
          if (f2 && f2.complete) {
            img = f2;
            break;
          }
        }
      }

      if (img && img.complete) {
        blit(img);
      }

      animId = requestAnimationFrame(loop);
    };

    animId = requestAnimationFrame(loop);

    return () => {
      cancelled = true;
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", resize);
    };
  }, []);

  const highlight = FEATURE_HIGHLIGHTS[activeHighlightIndex];

  return (
    <div className="relative w-full h-full min-h-[500px] lg:min-h-full overflow-hidden bg-[#0d0f12] flex flex-col justify-between p-8 lg:p-12 select-none">
      {/* Canvas Layer */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full object-cover z-0 filter brightness-[0.92]"
        aria-hidden="true"
      />

      {/* Cinematic Dusk and Shadow Gradients */}
      <div
        className="absolute inset-0 z-1 pointer-events-none"
        style={{
          background:
            "linear-gradient(180deg, rgba(13,15,18,0.7) 0%, rgba(13,15,18,0.1) 40%, rgba(13,15,18,0.3) 70%, rgba(13,15,18,0.92) 100%)",
        }}
      />

      {/* Top Header Badge */}
      <div className="relative z-10 flex items-center justify-between">
        <div className="inline-flex items-center gap-3 px-4 py-2 rounded-full arch-glass">
          <BrandMark className="w-5 h-5 text-[#C5A77B]" />
          <span className="font-display font-medium text-xs tracking-wider uppercase text-[#FFFFFF]">
            Constriva Atelier
          </span>
        </div>

        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full arch-glass text-[11px] font-mono text-[#ffbf7a]">
          <span className="w-2 h-2 rounded-full bg-[#ffbf7a] animate-pulse-glow" />
          <span>LIVE 3D WALKTHROUGH</span>
        </div>
      </div>

      {/* Bottom Floating Glass Card with Animated Quote */}
      <div className="relative z-10 max-w-xl">
        <div className="arch-glass p-6 sm:p-8 rounded-3xl backdrop-blur-2xl border border-white/15">
          <div className="flex items-center justify-between gap-3 mb-3">
            <span className="inline-block px-3 py-1 rounded-full bg-white/10 text-[10px] font-mono uppercase tracking-widest text-[#C5A77B] border border-white/15">
              {highlight.tag}
            </span>
            <div className="flex items-center gap-1.5">
              {FEATURE_HIGHLIGHTS.map((_, idx) => (
                <span
                  key={idx}
                  className={`h-1.5 rounded-full transition-all duration-500 ${
                    idx === activeHighlightIndex ? "w-6 bg-[#C5A77B]" : "w-1.5 bg-white/20"
                  }`}
                />
              ))}
            </div>
          </div>

          <h3 className="font-display font-medium text-xl sm:text-2xl text-white tracking-tight leading-snug">
            {highlight.title}
          </h3>
          <p className="text-xs sm:text-sm text-white/80 mt-2 leading-relaxed">
            {highlight.description}
          </p>

          <div className="mt-5 pt-4 border-t border-white/10 flex items-center justify-between text-[11px] font-mono text-white/60">
            <span>421 Frames // Continuous Take</span>
            <span className="text-[#ffbf7a]">₹0 API Cost Engine</span>
          </div>
        </div>
      </div>
    </div>
  );
}

