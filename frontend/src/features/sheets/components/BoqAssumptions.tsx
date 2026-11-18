/**
 * The assumptions behind the bill on screen, and the controls to change them.
 *
 * Every control shows the value the bill was calculated with (`assumptions`, from the
 * server). A change asks for the bill again with the complete set of the person's choices:
 * `choices` (what the bill on screen was calculated with) plus the field just changed. A
 * field the person never touched is left out, so the server's default applies. The only
 * state kept here is what was typed or picked and is not in the bill yet.
 */
import { type FocusEvent, type KeyboardEvent, type Ref, useEffect, useId, useRef, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { AlertCircleIcon } from '../../../components/ui/Icons';
import { Input } from '../../../components/ui/Input';
import type {
  BoqAssumptions as AssumptionsInUse,
  BoqAssumptionsInput,
  BoqBuildingType,
  BoqTilePattern,
  BoqTileSize,
} from '../boqSchemas';

interface Option<T extends string> {
  value: T;
  label: string;
}

const BUILDING_TYPES: readonly Option<BoqBuildingType>[] = [
  { value: 'villa', label: 'Villa' },
  { value: 'apartment', label: 'Apartment' },
  { value: 'other', label: 'Other' },
];

const TILE_SIZES: readonly Option<BoqTileSize>[] = [
  { value: '600x600', label: '600 x 600 mm' },
  { value: '800x800', label: '800 x 800 mm' },
  { value: '1200x600', label: '1200 x 600 mm' },
];

const TILE_PATTERNS: readonly Option<BoqTilePattern>[] = [
  { value: 'standard', label: 'Standard (5% waste)' },
  { value: 'herringbone', label: 'Herringbone (15% waste)' },
];

const BUILDING_TYPE_SOURCES = new Map([
  ['user', 'Set by you'],
  ['plan', 'From the plan'],
  ['default', 'Default: the plan states none'],
]);

const CEILING_HEIGHT_SOURCES = new Map([
  ['user', ' on every level, set by you'],
  ['plan', ' from the plan'],
  ['assumed', ' assumed: the plan states none'],
  ['mixed', ' per level: from the plan where stated, otherwise assumed'],
]);

const NUMBER_FIELDS = ['ceiling_height_m', 'false_ceiling_share', 'plot_perimeter_m'] as const;
type NumberField = (typeof NUMBER_FIELDS)[number];
type Field = NumberField | 'building_type' | 'tile_size_mm' | 'tile_pattern';

/** What was typed or picked and is not in the bill on screen (yet). */
type Edits = Partial<Record<Field, string>>;
/** Why a typed number was not sent. */
type Problems = Partial<Record<NumberField, string>>;

interface NumberRule {
  min: number;
  /** False when the value must be above `min`. */
  minAllowed: boolean;
  max: number;
  /** An empty field is a choice too: "the default". */
  emptyAllowed: boolean;
  problem: string;
}

/** The same limits as the server. The false ceiling is typed as a percentage, sent as a share. */
const NUMBER_RULES: Record<NumberField, NumberRule> = {
  ceiling_height_m: {
    min: 2,
    minAllowed: true,
    max: 8,
    emptyAllowed: true,
    problem: 'Enter a height from 2 to 8 m, or leave it empty to use the plan.',
  },
  false_ceiling_share: {
    min: 0,
    minAllowed: true,
    max: 100,
    emptyAllowed: false,
    problem: 'Enter a percentage from 0 to 100.',
  },
  plot_perimeter_m: {
    min: 0,
    minAllowed: false,
    max: 100_000,
    emptyAllowed: true,
    problem: 'Enter a perimeter above 0 m (100,000 m at most), or leave it empty to estimate it from the plan.',
  },
};

const toPercent = (share: number) => Number((share * 100).toFixed(4));
const toShare = (percent: number) => Number((percent / 100).toFixed(6));

/** The number in a field: null for a field left empty, undefined when it cannot be used. */
function readNumber(field: NumberField, text: string): number | null | undefined {
  const rule = NUMBER_RULES[field];
  const trimmed = text.trim();
  if (trimmed === '') return rule.emptyAllowed ? null : undefined;
  const value = Number(trimmed);
  if (!Number.isFinite(value)) return undefined;
  const highEnough = rule.minAllowed ? value >= rule.min : value > rule.min;
  return highEnough && value <= rule.max ? value : undefined;
}

/** What each control shows when nothing is being edited: the bill's own values. */
function valuesInUse(used: AssumptionsInUse): Record<Field, string> {
  // a height is the person's own only when they set it; otherwise the field is empty
  const ownHeight = used.ceiling_height_source === 'user' && used.ceiling_heights_m.length > 0;
  return {
    building_type: used.building_type,
    ceiling_height_m: ownHeight ? String(used.ceiling_heights_m[0]) : '',
    tile_size_mm: used.tile_size_mm,
    tile_pattern: used.tile_pattern,
    false_ceiling_share: String(toPercent(used.false_ceiling_share)),
    plot_perimeter_m: used.plot_perimeter_m === null ? '' : String(used.plot_perimeter_m),
  };
}

/** `choices` with one number set. A field left empty is left out, so the default applies. */
function withNumber(choices: BoqAssumptionsInput, field: NumberField, value: number | null): BoqAssumptionsInput {
  const next = { ...choices };
  if (value === null) delete next[field];
  else next[field] = field === 'false_ceiling_share' ? toShare(value) : value;
  return next;
}

/** "3.35 m assumed: the plan states none", "2.80 m, 3.10 m from the plan". */
function ceilingHeightHint(used: AssumptionsInUse): string | undefined {
  const heights = used.ceiling_heights_m.map((height) => `${height.toFixed(2)} m`);
  if (heights.length === 0) return undefined;
  // one height when every level has the same, otherwise one per level
  const shown = new Set(heights).size === 1 ? heights[0] : heights.join(', ');
  return `${shown}${CEILING_HEIGHT_SOURCES.get(used.ceiling_height_source) ?? ''}`;
}

const capitalised = (text: string) => (text ? text.charAt(0).toUpperCase() + text.slice(1) : 'Not stated');

const FIELD = 'flex min-w-0 flex-col gap-1.5';
const FIELD_LABEL = 'text-xs font-semibold uppercase tracking-wider text-[#A6A6A6]';
const DISABLED = 'disabled:cursor-not-allowed disabled:opacity-60';
const SELECT = `h-11 w-full rounded border border-[#303030] bg-[#181818] px-3 text-sm text-white transition-colors duration-150 focus:border-[#C5A77B] focus:outline-none ${DISABLED}`;
const NUMBER_INPUT = `${DISABLED} aria-invalid:border-[#FFB4AB] aria-invalid:focus:border-[#FFB4AB]`;

const hintId = (id: string) => `${id}-hint`;
const problemId = (id: string) => `${id}-problem`;

function FieldNotes({ id, hint, problem }: { id: string; hint?: string; problem?: string }) {
  return (
    <>
      {hint && (
        <p id={hintId(id)} className="m-0 break-words text-xs text-[#A6A6A6]">
          {hint}
        </p>
      )}
      {problem && (
        <p id={problemId(id)} role="alert" className="m-0 text-xs text-[#FFB4AB]">
          {problem}
        </p>
      )}
    </>
  );
}

interface SelectFieldProps<T extends string> {
  id: string;
  label: string;
  /** The value in use; shown as an option of its own when it is none of `options`. */
  value: string;
  options: readonly Option<T>[];
  /** How to name a value in use that is none of the options (a building type the plan states, say). */
  otherLabel: (value: string) => string;
  hint?: string;
  disabled: boolean;
  selectRef?: Ref<HTMLSelectElement>;
  onPick: (value: T, control: HTMLSelectElement) => void;
}

function SelectField<T extends string>(props: SelectFieldProps<T>) {
  const { id, label, value, options, otherLabel, hint, disabled, selectRef, onPick } = props;
  const known = options.some((option) => option.value === value);
  return (
    <div className={FIELD}>
      <label htmlFor={id} className={FIELD_LABEL}>
        {label}
      </label>
      <select
        id={id}
        ref={selectRef}
        value={value}
        disabled={disabled}
        aria-describedby={hint ? hintId(id) : undefined}
        onChange={(e) => {
          const picked = options.find((option) => option.value === e.target.value);
          if (picked) onPick(picked.value, e.currentTarget);
        }}
        className={SELECT}
      >
        {!known && <option value={value}>{otherLabel(value)}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <FieldNotes id={id} hint={hint} />
    </div>
  );
}

interface NumberFieldProps {
  id: string;
  label: string;
  value: string;
  rule: NumberRule;
  placeholder?: string;
  hint?: string;
  problem?: string;
  disabled: boolean;
  onType: (text: string) => void;
  onBlur: (e: FocusEvent<HTMLInputElement>) => void;
  onKeyDown: (e: KeyboardEvent<HTMLInputElement>) => void;
}

function NumberInputField(props: NumberFieldProps) {
  const { id, label, value, rule, placeholder, hint, problem, disabled, onType, onBlur, onKeyDown } = props;
  const describedBy = [hint && hintId(id), problem && problemId(id)].filter(Boolean).join(' ');
  return (
    <div className={FIELD}>
      <Input
        id={id}
        type="number"
        inputMode="decimal"
        step="any"
        min={rule.min}
        max={rule.max}
        label={label}
        placeholder={placeholder}
        autoComplete="off"
        value={value}
        disabled={disabled}
        aria-invalid={problem ? true : undefined}
        aria-describedby={describedBy || undefined}
        className={NUMBER_INPUT}
        onChange={(e) => onType(e.target.value)}
        onBlur={onBlur}
        onKeyDown={onKeyDown}
      />
      <FieldNotes id={id} hint={hint} problem={problem} />
    </div>
  );
}

interface BoqAssumptionsProps {
  /** The values the bill on screen was calculated with. */
  assumptions: AssumptionsInUse;
  /** The person's own choices behind that bill; empty when they changed nothing. */
  choices: BoqAssumptionsInput;
  /** A recalculation is in flight. */
  busy: boolean;
  /** Why the last recalculation failed; the bill on screen is still the one before it. */
  error: string | null;
  /** Calculate the bill again with this complete set of choices. */
  onRecalculate: (choices: BoqAssumptionsInput) => void;
}

export function BoqAssumptions({ assumptions, choices, busy, error, onRecalculate }: BoqAssumptionsProps) {
  const baseId = useId();
  const [edits, setEdits] = useState<Edits>({});
  const [problems, setProblems] = useState<Problems>({});
  const [wasBusy, setWasBusy] = useState(busy);
  const panel = useRef<HTMLElement>(null);
  const firstControl = useRef<HTMLSelectElement>(null);
  /** The control to give the keyboard focus back to when the request is over. */
  const focusAfter = useRef<HTMLElement | null>(null);

  if (wasBusy !== busy) {
    setWasBusy(busy);
    if (!busy) {
      // The request is over: the controls show the bill's own values again, whether it
      // worked or not. A number that was refused stays, next to its message.
      const kept: Edits = {};
      for (const field of NUMBER_FIELDS) {
        if (problems[field] !== undefined && edits[field] !== undefined) kept[field] = edits[field];
      }
      setEdits(kept);
    }
  }

  // A disabled control drops the keyboard focus. Give it back once the controls work again,
  // unless the person has moved on to something else in the meantime.
  useEffect(() => {
    if (busy) return;
    const target = focusAfter.current;
    focusAfter.current = null;
    if (!target) return;
    const active = document.activeElement;
    if (active && active !== document.body && active !== target) return;
    // "Reset to defaults" is gone once it has worked: the first control takes its place
    (target.isConnected ? target : firstControl.current)?.focus({ preventScroll: true });
  }, [busy]);

  const inUse = valuesInUse(assumptions);
  const shown = (field: Field) => edits[field] ?? inUse[field];
  const id = (field: Field) => `${baseId}-${field}`;
  const titleId = `${baseId}-title`;

  const send = (next: BoqAssumptionsInput, focus: HTMLElement | null) => {
    focusAfter.current = focus;
    onRecalculate(next);
  };

  /** A pick in a select recalculates at once; the pick stays visible while the request runs. */
  const pick = (field: Field, value: string, next: BoqAssumptionsInput, control: HTMLElement) => {
    setEdits({ ...edits, [field]: value });
    send(next, control);
  };

  const edit = (field: NumberField, text: string) => {
    setEdits({ ...edits, [field]: text });
    if (problems[field] !== undefined) {
      const rest = { ...problems };
      delete rest[field];
      setProblems(rest);
    }
  };

  /** A number is sent when the person is done with it: only a valid one, and only when it changed. */
  const commit = (field: NumberField, input: HTMLInputElement, focus: HTMLElement | null) => {
    if (busy) return;
    const text = edits[field];
    // text the browser cannot read as a number never reaches `edits`: the input reports it
    if (text === undefined && !input.validity.badInput) return;
    const value = input.validity.badInput ? undefined : readNumber(field, text ?? '');
    if (value === undefined) {
      setProblems({ ...problems, [field]: NUMBER_RULES[field].problem });
      return;
    }
    if (value === readNumber(field, inUse[field])) {
      // the value the bill already has: show it the way the bill has it
      const rest = { ...edits };
      delete rest[field];
      setEdits(rest);
      return;
    }
    send(withNumber(choices, field, value), focus);
  };

  const numberField = (field: NumberField) => ({
    id: id(field),
    value: shown(field),
    rule: NUMBER_RULES[field],
    problem: problems[field],
    disabled: busy,
    onType: (text: string) => edit(field, text),
    onBlur: (e: FocusEvent<HTMLInputElement>) => {
      // focus that moves on to another control of the panel is lost when that control is disabled
      const next = e.relatedTarget;
      commit(field, e.currentTarget, next instanceof HTMLElement && panel.current?.contains(next) ? next : null);
    },
    onKeyDown: (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') commit(field, e.currentTarget, e.currentTarget);
    },
  });

  const reset = (button: HTMLElement) => {
    setEdits({});
    setProblems({});
    send({}, button);
  };

  return (
    <section
      ref={panel}
      aria-labelledby={titleId}
      className="flex flex-col gap-4 rounded border border-[#303030] bg-[#141414] p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 id={titleId} className="font-display text-lg font-semibold text-white">
              Assumptions
            </h2>
            <div role="status" aria-live="polite" className="font-mono text-xs text-[#C5A77B]">
              {busy ? 'Recalculating...' : ''}
            </div>
          </div>
          <p className="m-0 text-xs leading-relaxed text-[#A6A6A6]">
            Changing these recalculates the quantities. The drawing is not read again.
          </p>
        </div>
        {Object.keys(choices).length > 0 && (
          <Button variant="secondary" size="sm" className="shrink-0" disabled={busy} onClick={(e) => reset(e.currentTarget)}>
            Reset to defaults
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-x-3 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
        <SelectField
          id={id('building_type')}
          label="Building type"
          value={shown('building_type')}
          options={BUILDING_TYPES}
          otherLabel={capitalised}
          hint={BUILDING_TYPE_SOURCES.get(assumptions.building_type_source)}
          disabled={busy}
          selectRef={firstControl}
          onPick={(value, control) => pick('building_type', value, { ...choices, building_type: value }, control)}
        />
        <NumberInputField
          {...numberField('ceiling_height_m')}
          label="Ceiling height (m)"
          placeholder="From the plan"
          hint={ceilingHeightHint(assumptions)}
        />
        <SelectField
          id={id('tile_size_mm')}
          label="Tile size"
          value={shown('tile_size_mm')}
          options={TILE_SIZES}
          otherLabel={(value) => `${value.replace(/x/gi, ' x ')} mm`}
          disabled={busy}
          onPick={(value, control) => pick('tile_size_mm', value, { ...choices, tile_size_mm: value }, control)}
        />
        <SelectField
          id={id('tile_pattern')}
          label="Tile pattern"
          value={shown('tile_pattern')}
          options={TILE_PATTERNS}
          otherLabel={capitalised}
          disabled={busy}
          onPick={(value, control) => pick('tile_pattern', value, { ...choices, tile_pattern: value }, control)}
        />
        <NumberInputField {...numberField('false_ceiling_share')} label="False ceiling (% of dry area)" />
        <NumberInputField
          {...numberField('plot_perimeter_m')}
          label="Plot perimeter (m)"
          placeholder="Estimated from the plan"
          hint={assumptions.plot_perimeter_m === null ? 'Estimated from the plan' : 'Set by you'}
        />
      </div>

      {error && (
        <div role="alert" className="flex items-start gap-2 rounded border border-[#FFB4AB]/40 bg-[#351010] p-3 text-xs text-[#FFB4AB]">
          <AlertCircleIcon size={16} className="mt-px shrink-0" aria-hidden="true" />
          <span className="min-w-0 break-words leading-relaxed">{error}</span>
        </div>
      )}
    </section>
  );
}
