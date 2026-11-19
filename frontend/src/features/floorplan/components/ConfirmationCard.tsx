/**
 * "Is this right?": what was understood before anything is drawn, styled for the chat
 * studio. Conflicts, assumptions and unknowns are listed so nothing is decided silently.
 * The villa and owner names go into the plan's title block (PROJECT / OWNER).
 */
import type { ReactNode } from 'react';
import { Icon } from '../../studio/icons';
import { POOL_LAYOUTS, type ParseResponse } from '../schemas';

const ROOM_NAMES: Record<string, string> = {
  master_bedroom: 'Master bedroom',
  bedroom: 'Bedroom',
  family_hall: 'Family hall',
  maid_room: 'Maid room',
  deck: 'Sit-out',
  pool: 'Swimming pool',
  toilet: 'Guest toilet',
};

function roomName(type: string): string {
  return ROOM_NAMES[type] ?? type.charAt(0).toUpperCase() + type.slice(1).replace(/_/g, ' ');
}

function plotText(p: ParseResponse['brief']['plot']): string {
  if (!p.width_cm || !p.depth_cm) return 'not given';
  if (p.input_unit === 'm') return `${+(p.width_cm / 100).toFixed(2)} × ${+(p.depth_cm / 100).toFixed(2)} m`;
  const ft = (cm: number) => {
    const inches = Math.round(cm / 2.54);
    const f = Math.floor(inches / 12);
    const i = inches % 12;
    return i ? `${f}'${i}"` : `${f}'`;
  };
  return `${ft(p.width_cm)} × ${ft(p.depth_cm)}`;
}

function List({ title, items, tone }: { title: string; items: string[]; tone: 'warn' | 'info' | 'error' }) {
  if (!items.length) return null;
  return (
    <div className="st-blist" data-tone={tone}>
      <h4>{title}</h4>
      <ul>
        {items.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ul>
    </div>
  );
}

export interface PlanNames {
  project: string;
  owner: string;
}

interface Props {
  parsed: ParseResponse;
  busy: boolean;
  onBack: () => void;
  onGenerate: () => void;
  /** Villa and owner names for the title block; editable while the card is current. */
  names?: PlanNames;
  onNames?: (n: PlanNames) => void;
  footer?: ReactNode;
}

export function ConfirmationCard({ parsed, busy, onBack, onGenerate, names, onNames, footer }: Props) {
  const b = parsed.brief;
  const rows: [string, string][] = [
    ['Plot', plotText(b.plot) + (b.plot.shape_assumed ? ' (shape assumed from the area)' : '')],
    ['Bedrooms', b.bedrooms == null ? 'not given' : String(b.bedrooms)],
    ['Bathrooms', b.bathrooms == null ? 'decided by the plan' : String(b.bathrooms)],
    ['Road side', b.road_side ?? 'not given'],
  ];
  if (b.rooms.some((r) => r.type === 'pool')) {
    const layout = POOL_LAYOUTS.find((p) => p.value === (b.pool_layout ?? 'side'));
    if (layout) rows.push(['Pool', `${layout.label} (${layout.hint})`]);
  }
  if (!names) {
    if (b.project_name) rows.push(['Project', b.project_name]);
    if (b.owner_name) rows.push(['Owner', b.owner_name]);
  }
  const conflicts = b.conflicts.map(
    (c) => `${c.field}: the form said ${c.form_value}, the description said ${c.text_value}; ${c.resolution}.`,
  );
  const editable = !!onNames && !busy;

  return (
    <section aria-labelledby="fp-confirm-title" className="st-card st-brief">
      <header className="st-brief-head">
        <span className="st-brief-icon" aria-hidden="true">
          <Icon name="plan" small />
        </span>
        <div>
          <h3 id="fp-confirm-title">Is this right?</h3>
          <p>{parsed.summary}</p>
        </div>
      </header>

      <div className="st-brief-body">
        <dl className="st-kv">
          {rows.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>

        {b.rooms.length > 0 && (
          <div className="st-tags" aria-label="Rooms">
            {b.rooms.map((r, i) => (
              <span key={`${r.type}-${i}`} className="st-tag">
                {r.count > 1 ? `${r.count}× ` : ''}
                {r.label ?? roomName(r.type)}
                {r.attached_bath ? ' + attached bath' : ''}
                {r.dress_room ? ' + dress' : ''}
              </span>
            ))}
          </div>
        )}

        {names && (
          <div className="st-names">
            <label className="st-field">
              <span>Villa / project name</span>
              <input
                value={names.project}
                maxLength={120}
                placeholder="e.g. Granite Villa"
                disabled={!editable}
                onChange={(e) => onNames?.({ ...names, project: e.target.value })}
              />
            </label>
            <label className="st-field">
              <span>Owner name</span>
              <input
                value={names.owner}
                maxLength={120}
                placeholder="e.g. Mr. A. Sharma"
                disabled={!editable}
                onChange={(e) => onNames?.({ ...names, owner: e.target.value })}
              />
            </label>
            <p className="st-names-hint">Printed in the title block of the plan, next to the total area.</p>
          </div>
        )}

        <List title="Needed before drawing" items={parsed.missing} tone="error" />
        <List title="Form and description disagree" items={conflicts} tone="warn" />
        <List title="Please note" items={[...parsed.warnings, ...b.unknowns]} tone="warn" />
        <List title="Assumed" items={b.assumptions} tone="info" />

        {footer}
      </div>

      <footer className="st-brief-actions">
        <button type="button" className="st-btn" onClick={onBack} disabled={busy}>
          <Icon name="pen" small />
          Change
        </button>
        <button
          type="button"
          className="st-btn st-btn-primary"
          disabled={!parsed.ready || busy}
          aria-busy={busy || undefined}
          onClick={onGenerate}
        >
          <Icon name="spark" small />
          Generate plan
        </button>
      </footer>
    </section>
  );
}
