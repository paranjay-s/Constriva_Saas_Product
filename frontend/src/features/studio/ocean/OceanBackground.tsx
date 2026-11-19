/**
 * The animated ASCII background, plus a small context so the chat can talk to it:
 * typing() while the person types, setWorking() while the AI works, pulse() when a result
 * arrives, dim() on a mistake, setFacing() when a plan turns.
 */
import { createContext, useContext, useEffect, useMemo, useRef, type ReactNode } from 'react';
import { AsciiOcean } from './AsciiOcean';
import type { Theme } from './forms';

export interface OceanControls {
  typing: () => void;
  pulse: () => void;
  dim: () => void;
  setWorking: (on: boolean) => void;
  setFacing: (side: string | null | undefined) => void;
  /** The composer's centre, where ripples start. */
  setTarget: (el: HTMLElement | null) => void;
}

const noop: OceanControls = {
  typing: () => {},
  pulse: () => {},
  dim: () => {},
  setWorking: () => {},
  setFacing: () => {},
  setTarget: () => {},
};

const OceanContext = createContext<OceanControls>(noop);
export const useOcean = () => useContext(OceanContext);

interface Props {
  theme: Theme;
  playing: boolean;
  children: ReactNode;
}

export function OceanProvider({ theme, playing, children }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const engine = useRef<AsciiOcean | null>(null);
  const targetEl = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!host.current || !canvas.current) return;
    const o = new AsciiOcean(host.current, canvas.current);
    engine.current = o;
    if (!o.supported || typeof ResizeObserver === 'undefined') return () => o.destroy();
    const el = host.current;
    const place = () => {
      o.resize();
      const t = targetEl.current;
      if (t) {
        const r = t.getBoundingClientRect(), h = el.getBoundingClientRect();
        o.setTarget(r.left - h.left + r.width / 2, r.top - h.top + r.height / 2);
      }
    };
    const ro = new ResizeObserver(() => requestAnimationFrame(place));
    ro.observe(el);
    const move = (e: PointerEvent) => {
      if (e.pointerType === 'touch') return;
      const h = el.getBoundingClientRect();
      o.setPointer(e.clientX - h.left, e.clientY - h.top);
    };
    const leave = () => o.setPointer(-1e5, -1e5);
    window.addEventListener('pointermove', move, { passive: true });
    document.documentElement.addEventListener('pointerleave', leave);
    place();
    document.fonts?.load?.('500 11px "Geist Mono"').then(() => o.redraw()).catch(() => {});
    return () => {
      ro.disconnect();
      window.removeEventListener('pointermove', move);
      document.documentElement.removeEventListener('pointerleave', leave);
      o.destroy();
      engine.current = null;
    };
  }, []);

  useEffect(() => {
    engine.current?.setTheme(theme);
  }, [theme]);

  useEffect(() => {
    engine.current?.setPlaying(playing);
  }, [playing]);

  const controls = useMemo<OceanControls>(
    () => ({
      typing: () => engine.current?.typing(),
      pulse: () => engine.current?.pulse(),
      dim: () => engine.current?.dim(),
      setWorking: (on) => engine.current?.setWorking(on),
      setFacing: (side) => engine.current?.setFacing(side),
      setTarget: (el) => {
        targetEl.current = el;
        const h = host.current, o = engine.current;
        if (el && h && o) {
          const r = el.getBoundingClientRect(), hr = h.getBoundingClientRect();
          o.setTarget(r.left - hr.left + r.width / 2, r.top - hr.top + r.height / 2);
        }
      },
    }),
    [],
  );

  return (
    <OceanContext.Provider value={controls}>
      <div ref={host} className="studio-ocean" aria-hidden="true">
        <canvas ref={canvas} />
      </div>
      {children}
    </OceanContext.Provider>
  );
}
