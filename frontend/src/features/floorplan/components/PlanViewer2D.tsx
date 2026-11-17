/**
 * The drawing, with zoom (wheel, pinch-free buttons) and pan (drag). The SVG from the API
 * is shown through an <img> blob URL, so it can never run script in the page.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { IconMaximize, IconZoomIn, IconZoomOut } from '../../../components/ui/Icons';

const MIN = 0.5;
const MAX = 8;

export function PlanViewer2D({ svg, title }: { svg: string; title: string }) {
  const url = useMemo(() => URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' })), [svg]);
  useEffect(() => () => URL.revokeObjectURL(url), [url]);

  const [view, setView] = useState({ scale: 1, x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);
  const box = useRef<HTMLDivElement>(null);

  // A new drawing keeps the zoom: edits are easier to compare that way.
  const zoomAt = (factor: number, cx?: number, cy?: number) =>
    setView((v) => {
      const scale = Math.min(MAX, Math.max(MIN, v.scale * factor));
      const rect = box.current?.getBoundingClientRect();
      const px = cx ?? (rect ? rect.width / 2 : 0);
      const py = cy ?? (rect ? rect.height / 2 : 0);
      const k = scale / v.scale;
      return { scale, x: px - (px - v.x) * k, y: py - (py - v.y) * k };
    });

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - rect.left, e.clientY - rect.top);
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  const tool =
    'flex h-8 w-8 cursor-pointer items-center justify-center rounded-md border border-[#2A2F38] bg-[#16181E]/90 text-[#D5DAE1] hover:border-[#C5A77B]';

  return (
    <div className="relative h-full min-h-[420px] w-full overflow-hidden rounded-lg border border-[#23272F] bg-white">
      <div
        ref={box}
        className="h-full w-full cursor-grab touch-none active:cursor-grabbing"
        onPointerDown={(e) => {
          (e.target as Element).setPointerCapture?.(e.pointerId);
          drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
        }}
        onPointerMove={(e) => {
          const d = drag.current;
          if (d) setView((v) => ({ ...v, x: d.vx + e.clientX - d.x, y: d.vy + e.clientY - d.y }));
        }}
        onPointerUp={() => (drag.current = null)}
        onPointerCancel={() => (drag.current = null)}
        onDoubleClick={() => setView({ scale: 1, x: 0, y: 0 })}
      >
        <img
          src={url}
          alt={title}
          draggable={false}
          className="pointer-events-none h-full w-full select-none object-contain"
          style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`, transformOrigin: '0 0' }}
        />
      </div>
      <div className="absolute right-3 top-3 flex flex-col gap-1.5">
        <button type="button" className={tool} onClick={() => zoomAt(1.25)} aria-label="Zoom in">
          <IconZoomIn className="h-4 w-4" />
        </button>
        <button type="button" className={tool} onClick={() => zoomAt(1 / 1.25)} aria-label="Zoom out">
          <IconZoomOut className="h-4 w-4" />
        </button>
        <button type="button" className={tool} onClick={() => setView({ scale: 1, x: 0, y: 0 })} aria-label="Fit to view">
          <IconMaximize className="h-4 w-4" />
        </button>
      </div>
      <p className="pointer-events-none absolute bottom-2 left-3 text-[11px] text-[#7D8594]">
        Scroll to zoom · drag to move · double-click to fit
      </p>
    </div>
  );
}
