/**
 * "Project: ..." button in the composer. Opens a small menu with the user's saved projects
 * and "New project". A floor plan can only be generated inside a project.
 */
import { useEffect, useRef, useState } from 'react';
import type { Project } from '../../types';
import { Icon } from './icons';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** A project that really exists in the user's account (not a local placeholder). */
export function isSavedProject(p: Project | null | undefined, projects: Project[]): p is Project {
  return Boolean(p && UUID_RE.test(p.id) && projects.some((x) => x.id === p.id));
}

interface Props {
  project: Project | null;
  projects: Project[];
  loading: boolean;
  error: string | null;
  highlight?: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onChoose: (p: Project) => void;
  onCreate: () => void;
  onRetry: () => void;
}

export function ProjectMenu(p: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const [focusIdx, setFocusIdx] = useState(0);
  const saved = p.projects.filter((x) => UUID_RE.test(x.id));
  const { open, onOpenChange } = p;

  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => {
      if (!wrap.current?.contains(e.target as Node)) onOpenChange(false);
    };
    const esc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpenChange(false);
    };
    window.addEventListener('pointerdown', away);
    window.addEventListener('keydown', esc);
    return () => {
      window.removeEventListener('pointerdown', away);
      window.removeEventListener('keydown', esc);
    };
  }, [open, onOpenChange]);

  useEffect(() => {
    if (open) wrap.current?.querySelectorAll<HTMLButtonElement>('[data-opt]')[focusIdx]?.focus();
  }, [open, focusIdx]);

  return (
    <div ref={wrap} style={{ position: 'relative' }}>
      <button
        type="button"
        className="st-chipbtn"
        aria-haspopup="menu"
        aria-expanded={open}
        data-missing={p.highlight && !p.project ? '' : undefined}
        onClick={() => {
          setFocusIdx(0);
          onOpenChange(!open);
        }}
      >
        <Icon name="folder" small />
        <span className="st-cname">{p.project ? p.project.name : 'Choose project'}</span>
        <Icon name="chevron" small />
      </button>
      {open && (
        <div
          role="menu"
          aria-label="Projects"
          onKeyDown={(e) => {
            const n = saved.length + 1;
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              setFocusIdx((i) => (i + 1) % n);
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              setFocusIdx((i) => (i - 1 + n) % n);
            }
          }}
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 8px)',
            left: 0,
            zIndex: 40,
            width: 300,
            maxHeight: 320,
            overflowY: 'auto',
            padding: 6,
            borderRadius: 14,
            border: '1px solid var(--border-strong)',
            background: 'rgba(9,12,18,.97)',
            boxShadow: '0 30px 80px -20px rgba(0,0,0,.9)',
          }}
        >
          <p className="st-heading" style={{ padding: '6px 8px' }}>
            save the plan in
          </p>
          {p.loading && saved.length === 0 && <p className="st-hempty">Loading your projects…</p>}
          {p.error && (
            <p className="st-hempty" role="alert">
              {p.error}{' '}
              <button type="button" onClick={p.onRetry} style={{ textDecoration: 'underline' }}>
                Try again
              </button>
            </p>
          )}
          {saved.map((x, i) => (
            <button
              key={x.id}
              type="button"
              role="menuitemradio"
              aria-checked={p.project?.id === x.id}
              data-opt
              tabIndex={i === focusIdx ? 0 : -1}
              className="st-hlink"
              style={{ paddingRight: 10 }}
              onClick={() => {
                p.onChoose(x);
                onOpenChange(false);
              }}
            >
              <span className="st-kind" data-kind="plan" aria-hidden="true">
                <Icon name="folder" small />
              </span>
              <span className="st-htitle">{x.name}</span>
              {p.project?.id === x.id && <span style={{ marginLeft: 'auto', color: 'var(--accent)' }}>✓</span>}
            </button>
          ))}
          <button
            type="button"
            role="menuitem"
            data-opt
            tabIndex={focusIdx === saved.length ? 0 : -1}
            className="st-hlink"
            style={{ color: 'var(--accent)', paddingRight: 10 }}
            onClick={() => {
              onOpenChange(false);
              p.onCreate();
            }}
          >
            <span className="st-kind" aria-hidden="true">
              <Icon name="plus" small />
            </span>
            New project
          </button>
        </div>
      )}
    </div>
  );
}
