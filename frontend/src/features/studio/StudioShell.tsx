/**
 * The studio layout shared by both agents, in the style of today's assistants:
 *
 *   [ sidebar | conversation (centred) | resizable side panel with the drawing / results ]
 *
 * The ASCII background sits behind the conversation. The side panel opens only when there
 * is something to look at, and can be resized (drag or arrow keys) or closed.
 */
import { createContext, type ReactNode, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Icon } from './icons';
import { OceanProvider } from './ocean/OceanBackground';
import type { Theme } from './ocean/forms';
import { Rail } from './Rail';
import { type ChatKind, useChatHistory } from './useChatHistory';
import { useMotion } from './useMotion';
import './studio.css';

interface StudioContextValue {
  refreshHistory: () => void;
  motionOn: boolean;
  userName: string;
}
const StudioContext = createContext<StudioContextValue>({ refreshHistory: () => {}, motionOn: true, userName: '' });
export const useStudio = () => useContext(StudioContext);

export interface PanelSpec {
  title: string;
  actions?: ReactNode;
  body: ReactNode;
}

interface Props {
  theme: Theme;
  agent: ChatKind;
  currentId: string | null;
  title?: string;
  meta?: string;
  topActions?: ReactNode;
  chatting: boolean;
  panel: PanelSpec | null;
  onClosePanel: () => void;
  children: ReactNode;
}

const RAIL_KEY = 'constriva:rail';
const PANEL_KEY = 'constriva:panel';
const MIN_PANEL = 360;
const MIN_CHAT = 380;

function stored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function store(key: string, v: string) {
  try {
    localStorage.setItem(key, v);
  } catch {
    // not remembered
  }
}

export function StudioShell(p: Props) {
  const { user } = useAuth();
  const userName = user?.name || 'there';
  const [motionOn, toggleMotion] = useMotion();
  const history = useChatHistory();
  const [expanded, setExpanded] = useState(() => stored(RAIL_KEY) === 'open');
  const [drawer, setDrawer] = useState(false);
  const main = useRef<HTMLDivElement>(null);
  const [share, setShare] = useState(() => {
    const v = Number(stored(PANEL_KEY));
    return v > 0.2 && v < 0.8 ? v : 0.55;
  });
  const [mainW, setMainW] = useState(0);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const el = main.current;
    if (!el) return;
    setMainW(el.getBoundingClientRect().width);
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => setMainW(el.getBoundingClientRect().width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const panelW = mainW ? Math.round(Math.min(Math.max(mainW * share, MIN_PANEL), Math.max(MIN_PANEL, mainW - MIN_CHAT))) : 0;

  const startDrag = (e: React.PointerEvent) => {
    const el = main.current;
    if (!el) return;
    (e.target as Element).setPointerCapture?.(e.pointerId);
    setDragging(true);
    const rect = el.getBoundingClientRect();
    const move = (ev: PointerEvent) => {
      const w = rect.right - ev.clientX;
      setShare(Math.min(0.75, Math.max(0.25, w / rect.width)));
    };
    const up = () => {
      setDragging(false);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      setShare((s) => {
        store(PANEL_KEY, s.toFixed(3));
        return s;
      });
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  const toggleRail = () =>
    setExpanded((v) => {
      store(RAIL_KEY, v ? 'closed' : 'open');
      return !v;
    });

  const { refresh } = history;
  const refreshHistory = useCallback(() => void refresh(), [refresh]);

  return (
    <StudioContext.Provider value={{ refreshHistory, motionOn, userName }}>
      <div className="studio" data-theme={p.theme} data-rail={expanded ? 'expanded' : 'collapsed'} data-drawer={drawer ? 'open' : 'closed'}>
        <Rail
          agent={p.agent}
          currentId={p.currentId}
          history={history.items}
          historyLoading={history.loading}
          historyError={history.error}
          onRetryHistory={refreshHistory}
          onDelete={(item) => void history.remove(item)}
          expanded={expanded}
          onToggleExpanded={toggleRail}
          motionOn={motionOn}
          onToggleMotion={toggleMotion}
          userName={userName}
          onNavigate={() => setDrawer(false)}
        />
        {drawer && <div className="st-scrim" onClick={() => setDrawer(false)} />}

        <div className="st-main" ref={main} data-chat={p.chatting ? 'on' : 'off'}>
          <OceanProvider theme={p.theme} playing={motionOn}>
            <section className="st-chatcol" aria-label="Conversation">
              <header className="st-topbar">
                <button type="button" className="st-menu" aria-label="Open menu" aria-expanded={drawer} onClick={() => setDrawer(true)}>
                  <Icon name="menu" />
                </button>
                <div className="st-title">
                  {p.title && <h1>{p.title}</h1>}
                  {p.meta && <span className="st-meta">{p.meta}</span>}
                </div>
                {p.topActions}
              </header>
              {p.children}
            </section>

            {p.panel && (
              <>
                <div
                  className="st-divider"
                  role="separator"
                  aria-orientation="vertical"
                  aria-label="Resize the side panel"
                  aria-valuenow={Math.round(share * 100)}
                  aria-valuemin={25}
                  aria-valuemax={75}
                  tabIndex={0}
                  data-drag={dragging ? '' : undefined}
                  onPointerDown={startDrag}
                  onKeyDown={(e) => {
                    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
                    e.preventDefault();
                    setShare((s) => {
                      const v = Math.min(0.75, Math.max(0.25, s + (e.key === 'ArrowLeft' ? 0.03 : -0.03)));
                      store(PANEL_KEY, v.toFixed(3));
                      return v;
                    });
                  }}
                />
                <aside className="st-panel" style={{ width: panelW || undefined }} aria-label={p.panel.title}>
                  <div className="st-panel-head">
                    <h2>{p.panel.title}</h2>
                    {p.panel.actions}
                    <button type="button" className="st-icon-btn" aria-label="Close panel" title="Close" onClick={p.onClosePanel}>
                      <Icon name="x" />
                    </button>
                  </div>
                  <div className="st-panel-body">{p.panel.body}</div>
                </aside>
              </>
            )}
          </OceanProvider>
        </div>
      </div>
    </StudioContext.Provider>
  );
}

/** Empty state: greeting, headline, composer and starting points in the middle. */
export function Stage({ children, footnote }: { children: ReactNode; footnote?: string }) {
  return (
    <>
      <div className="st-stage">
        <div className="st-core">{children}</div>
      </div>
      {footnote && <p className="st-footnote">{footnote}</p>}
    </>
  );
}

/** Conversation state: the composer docked at the bottom. */
export function Dock({ children }: { children: ReactNode }) {
  return (
    <div className="st-dock">
      <div className="st-dock-inner">{children}</div>
    </div>
  );
}

export function Status({ tone, children }: { tone?: 'error'; children: ReactNode }) {
  return (
    <div className="st-status" data-tone={tone} role="status">
      <span className="st-dot" aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}
