/**
 * Greeting and rotating headline. Words blur out, the next line blurs in word by word
 * (Web Animations API). Screen readers hear one fixed line. Rotation stops while motion is
 * paused, the tab is hidden or the composer has text. *word* marks the accent.
 */
import { useEffect, useRef, useState } from 'react';

function daypart(): string {
  const h = new Date().getHours();
  return h >= 5 && h < 12 ? 'Good morning' : h >= 12 && h < 18 ? 'Good afternoon' : 'Good evening';
}

/** Words and the spaces between them; *accent* marks keep punctuation attached ("of?"). */
function words(line: string) {
  const out: { text: string; accent: boolean; space: boolean }[] = [];
  line.split(/(\*[^*]+\*)/).filter(Boolean).forEach((part) => {
    const accent = part.startsWith('*');
    part.replace(/\*/g, '').split(/(\s+)/).filter(Boolean).forEach((tok) => {
      out.push({ text: tok, accent, space: /^\s+$/.test(tok) });
    });
  });
  return out;
}

interface Props {
  name: string;
  lines: string[];
  playing: boolean;
  paused: boolean; // the composer has text
}

export function Headline({ name, lines, playing, paused }: Props) {
  const [idx, setIdx] = useState(0);
  const root = useRef<HTMLSpanElement>(null);
  const busy = useRef(false);
  const [visible, setVisible] = useState(() => (typeof document === 'undefined' ? true : !document.hidden));

  useEffect(() => {
    const on = () => setVisible(!document.hidden);
    document.addEventListener('visibilitychange', on);
    return () => document.removeEventListener('visibilitychange', on);
  }, []);

  useEffect(() => {
    if (!playing || paused || !visible || lines.length < 2) return;
    const el = root.current;
    if (!el || typeof el.animate !== 'function') return;
    const reduce = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      if (busy.current) return;
      busy.current = true;
      try {
        const cur = el.querySelector<HTMLElement>('.st-hl-line.is-on');
        if (cur) {
          await Promise.all(
            [...cur.querySelectorAll<HTMLElement>('.st-hl-w')].map(
              (w, i) =>
                w.animate(
                  reduce
                    ? [{ opacity: 1 }, { opacity: 0 }]
                    : [
                        { opacity: 1, filter: 'blur(0px)', transform: 'translateY(0) scale(1)' },
                        { opacity: 0, filter: 'blur(12px)', transform: 'translateY(-.22em) scale(.97)' },
                      ],
                  { duration: reduce ? 260 : 380, delay: reduce ? 0 : i * 26, easing: 'cubic-bezier(.55,0,.75,.35)', fill: 'forwards' },
                ).finished,
            ),
          );
          cur.getAnimations({ subtree: true }).forEach((a) => a.cancel());
        }
        if (cancelled) return;
        const next = (idx + 1) % lines.length;
        setIdx(next);
        requestAnimationFrame(() => {
          const nxt = el.querySelectorAll<HTMLElement>('.st-hl-line')[next];
          nxt?.querySelectorAll<HTMLElement>('.st-hl-w').forEach((w, i) =>
            w.animate(
              reduce
                ? [{ opacity: 0 }, { opacity: 1 }]
                : [
                    { opacity: 0, filter: 'blur(14px)', transform: 'translateY(.34em) scale(1.04)' },
                    { opacity: 0.7, filter: 'blur(4px)', offset: 0.45 },
                    { opacity: 1, filter: 'blur(0px)', transform: 'translateY(0) scale(1)' },
                  ],
              { duration: reduce ? 320 : 620, delay: reduce ? 0 : i * 46, easing: 'cubic-bezier(.16,1,.3,1)', fill: 'backwards' },
            ),
          );
        });
      } catch {
        // animation cancelled
      } finally {
        busy.current = false;
      }
    }, idx === 0 ? 2800 : 2200);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [idx, lines, playing, paused, visible]);

  return (
    <div className="st-intro">
      <div className="st-halo" aria-hidden="true" />
      <p className="st-eyebrow">
        <span className="st-dot" aria-hidden="true" />
        {daypart()}, {name}
      </p>
      <h1 className="st-h1">
        <span className="sr-only">{lines[0].replace(/\*/g, '')}</span>
        <span className="st-hl" ref={root} aria-hidden="true">
          {lines.map((line, i) => (
            <span key={line} className={`st-hl-line${i === idx ? ' is-on' : ''}`}>
              {words(line).map((w, j) =>
                w.space ? (
                  ' '
                ) : (
                  <span key={j} className={`st-hl-w${w.accent ? ' st-accent' : ''}`}>
                    {w.text}
                  </span>
                ),
              )}
            </span>
          ))}
        </span>
      </h1>
    </div>
  );
}
