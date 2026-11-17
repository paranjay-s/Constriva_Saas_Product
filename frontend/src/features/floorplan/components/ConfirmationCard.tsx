/**
 * Step 2: show what was understood before anything is drawn. Conflicts (description vs
 * form), assumptions and unknowns are listed so nothing is decided silently.
 */
import { Button } from '../../../components/ui/Button';
import { IconArrowLeft, IconSparkles } from '../../../components/ui/Icons';
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
  const color = { warn: 'text-[#F2C46D]', info: 'text-[#9AA3B2]', error: 'text-[#FFB4AB]' }[tone];
  return (
    <div>
      <h4 className={`mb-1 text-xs font-semibold uppercase tracking-wide ${color}`}>{title}</h4>
      <ul className="list-disc space-y-0.5 pl-5 text-sm text-[#D5DAE1]">
        {items.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ul>
    </div>
  );
}

interface Props {
  parsed: ParseResponse;
  busy: boolean;
  onBack: () => void;
  onGenerate: () => void;
}

export function ConfirmationCard({ parsed, busy, onBack, onGenerate }: Props) {
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
  if (b.project_name) rows.push(['Project', b.project_name]);
  if (b.owner_name) rows.push(['Owner', b.owner_name]);
  const conflicts = b.conflicts.map(
    (c) => `${c.field}: the form said ${c.form_value}, the description said ${c.text_value}; ${c.resolution}.`,
  );

  return (
    <section aria-labelledby="fp-confirm-title" className="flex flex-col gap-4">
      <div>
        <h3 id="fp-confirm-title" className="text-base font-semibold text-white">
          Is this right?
        </h3>
        <p className="text-sm text-[#9AA3B2]">{parsed.summary}</p>
      </div>

      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 rounded-md border border-[#23272F] bg-[#0F1115] p-3 text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-[#7D8594]">{k}</dt>
            <dd className="text-white">{v}</dd>
          </div>
        ))}
      </dl>

      {b.rooms.length > 0 && (
        <div className="flex flex-wrap gap-1.5" aria-label="Rooms">
          {b.rooms.map((r, i) => (
            <span key={`${r.type}-${i}`} className="rounded-full bg-[#1C1F26] px-2.5 py-1 text-xs text-[#D5DAE1]">
              {r.count > 1 ? `${r.count}× ` : ''}
              {r.label ?? roomName(r.type)}
              {r.attached_bath ? ' + attached bath' : ''}
              {r.dress_room ? ' + dress' : ''}
            </span>
          ))}
        </div>
      )}

      <List title="Needed before drawing" items={parsed.missing} tone="error" />
      <List title="Form and description disagree" items={conflicts} tone="warn" />
      <List title="Please note" items={[...parsed.warnings, ...b.unknowns]} tone="warn" />
      <List title="Assumed" items={b.assumptions} tone="info" />

      <div className="flex gap-2">
        <Button type="button" variant="secondary" onClick={onBack} leftIcon={<IconArrowLeft className="h-4 w-4" />}>
          Change
        </Button>
        <Button
          type="button"
          variant="accent"
          fullWidth
          disabled={!parsed.ready || busy}
          loading={busy}
          onClick={onGenerate}
          leftIcon={<IconSparkles className="h-4 w-4" />}
        >
          Generate plan
        </Button>
      </div>
    </section>
  );
}
