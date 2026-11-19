/**
 * Sidebar: new chats for both agents, projects, one history list (floor plans and image
 * analyses, grouped by day), pause motion, collapse and the profile. Collapses to icons on
 * desktop and becomes a drawer on phones.
 */
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { BrandMark } from '../../components/ui/Icons';
import { Icon } from './icons';
import { type ChatKind, type ChatSummary, dayGroup } from './useChatHistory';

interface Props {
  agent: ChatKind;
  currentId: string | null;
  history: ChatSummary[];
  historyLoading: boolean;
  historyError: string | null;
  onRetryHistory: () => void;
  onDelete: (item: ChatSummary) => void;
  expanded: boolean;
  onToggleExpanded: () => void;
  motionOn: boolean;
  onToggleMotion: () => void;
  userName: string;
  onNavigate: () => void;
}

type Filter = 'all' | ChatKind;

export function Rail(p: Props) {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>('all');
  const shown = p.history.filter((h) => filter === 'all' || h.kind === filter);
  const groups: [string, ChatSummary[]][] = [];
  for (const h of shown) {
    const g = dayGroup(h.createdAt);
    const last = groups[groups.length - 1];
    if (last && last[0] === g) last[1].push(h);
    else groups.push([g, [h]]);
  }
  const go = (href: string) => {
    p.onNavigate();
    navigate(href);
  };
  const initials = p.userName.trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase() || 'C';

  return (
    <aside className="st-rail" aria-label="Sidebar">
      <Link className="st-brand" to="/home" aria-label="Constriva home" title="Constriva home">
        <BrandMark />
        <span className="st-wordmark" aria-hidden="true">
          Constriva
        </span>
      </Link>

      <nav className="st-nav" aria-label="Workspace">
        <button
          type="button"
          className="st-item"
          aria-current={p.agent === 'plan' && !p.currentId ? 'page' : undefined}
          title="New floor plan"
          onClick={() => go('/projects/ai-generator')}
        >
          <Icon name="plan" />
          <span className="st-label">New floor plan</span>
        </button>
        <button
          type="button"
          className="st-item"
          aria-current={p.agent === 'analysis' && !p.currentId ? 'page' : undefined}
          title="New image analysis"
          onClick={() => go('/materials/analyse')}
        >
          <Icon name="image" />
          <span className="st-label">New image analysis</span>
        </button>
        <button type="button" className="st-item" title="Projects" onClick={() => go('/home')}>
          <Icon name="folder" />
          <span className="st-label">Projects</span>
        </button>
        <button
          type="button"
          className="st-item"
          title="History"
          onClick={() => {
            if (!p.expanded) p.onToggleExpanded();
          }}
        >
          <Icon name="history" />
          <span className="st-label">History</span>
        </button>
      </nav>

      <section className="st-history" aria-labelledby="st-history-heading">
        <div className="st-history-head">
          <h2 className="st-heading" id="st-history-heading">
            history
          </h2>
          <div className="st-filter" role="group" aria-label="Show">
            {(
              [
                ['all', 'All'],
                ['plan', 'Plans'],
                ['analysis', 'Images'],
              ] as const
            ).map(([v, label]) => (
              <button key={v} type="button" aria-pressed={filter === v} onClick={() => setFilter(v)}>
                {label}
              </button>
            ))}
          </div>
        </div>
        {p.historyLoading && p.history.length === 0 && <p className="st-hempty">Loading…</p>}
        {p.historyError && (
          <p className="st-hempty" role="alert">
            {p.historyError}{' '}
            <button type="button" onClick={p.onRetryHistory} style={{ textDecoration: 'underline' }}>
              Try again
            </button>
          </p>
        )}
        {!p.historyLoading && !p.historyError && shown.length === 0 && (
          <p className="st-hempty">Your floor plans and image analyses will appear here.</p>
        )}
        {groups.map(([label, list]) => (
          <div key={label}>
            <p className="st-group">{label}</p>
            <ul className="st-hlist">
              {list.map((h) => (
                <li key={`${h.kind}-${h.id}`} className="st-hrow">
                  <button
                    type="button"
                    className="st-hlink"
                    title={h.subtitle}
                    aria-current={h.id === p.currentId ? 'page' : undefined}
                    onClick={() => go(h.href)}
                  >
                    <span className="st-kind" data-kind={h.kind} aria-hidden="true">
                      <Icon name={h.kind === 'plan' ? 'plan' : 'image'} small />
                    </span>
                    <span className="st-htitle">{h.title}</span>
                    <span className="sr-only">({h.kind === 'plan' ? 'floor plan' : 'image analysis'})</span>
                  </button>
                  {h.kind === 'analysis' && (
                    <button
                      type="button"
                      className="st-hdel"
                      aria-label={`Delete ${h.title}`}
                      onClick={() => {
                        if (window.confirm('Delete this analysis and its chat?')) p.onDelete(h);
                      }}
                    >
                      <Icon name="trash" small />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <div className="st-foot">
        <button type="button" className="st-item" title={p.motionOn ? 'Pause motion' : 'Play motion'} onClick={p.onToggleMotion}>
          <Icon name={p.motionOn ? 'pause' : 'play'} />
          <span className="st-label">{p.motionOn ? 'Pause motion' : 'Play motion'}</span>
        </button>
        <button
          type="button"
          className="st-item st-collapse"
          title={p.expanded ? 'Collapse sidebar' : 'Expand sidebar'}
          aria-expanded={p.expanded}
          onClick={p.onToggleExpanded}
        >
          <Icon name="panel" />
          <span className="st-label">{p.expanded ? 'Collapse sidebar' : 'Expand sidebar'}</span>
        </button>
        <button type="button" className="st-item st-profile" title={p.userName} onClick={() => go('/home')}>
          <span className="st-avatar" aria-hidden="true">
            {initials}
          </span>
          <span className="st-label">
            {p.userName} <small>Your projects</small>
          </span>
        </button>
      </div>
    </aside>
  );
}
