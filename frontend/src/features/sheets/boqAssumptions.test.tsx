/**
 * The assumptions of a bill: the schema, the panel on its own, the page recalculating the
 * bill when one changes, and the job hook keeping the newest answer.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TOKEN_STORAGE_KEY } from '../../lib/api';
import { BoqPage } from './BoqPage';
import { BOQ_BASE } from './boqApi';
import { RAW_BOQ_RESULT } from './boqFixture';
import { type BoqAssumptionsInput, type BoqResult, boqAssumptionsSchema, boqResultSchema } from './boqSchemas';
import { BoqAssumptions } from './components/BoqAssumptions';
import { useBoqJob } from './hooks/useBoqJob';

const RAW_ASSUMPTIONS = RAW_BOQ_RESULT.assumptions;
const RECALCULATE = '/jobs/job-1/recalculate';

const LABELS = {
  building: 'Building type',
  height: 'Ceiling height (m)',
  tileSize: 'Tile size',
  tilePattern: 'Tile pattern',
  falseCeiling: 'False ceiling (% of dry area)',
  perimeter: 'Plot perimeter (m)',
} as const;

// ----------------------------------------------------------------- helpers

const panel = () => within(screen.getByRole('region', { name: 'Assumptions' }));

function select(label: string): HTMLSelectElement {
  const control = panel().getByLabelText(label);
  if (!(control instanceof HTMLSelectElement)) throw new Error(`${label} is not a <select>`);
  return control;
}

function field(label: string): HTMLInputElement {
  const control = panel().getByLabelText(label);
  if (!(control instanceof HTMLInputElement)) throw new Error(`${label} is not an <input>`);
  return control;
}

const optionsOf = (label: string) => Array.from(select(label).options).map((option) => option.textContent);

/** What a control is described by: its hint, then its validation message. */
const descriptionOf = (control: HTMLElement) =>
  (control.getAttribute('aria-describedby') ?? '')
    .split(' ')
    .filter(Boolean)
    .map((id) => document.getElementById(id)?.textContent ?? `(no element ${id})`);

const choose = (label: string, value: string) => fireEvent.change(select(label), { target: { value } });
const typeIn = (label: string, text: string) => fireEvent.change(field(label), { target: { value: text } });
const leave = (label: string) => fireEvent.blur(field(label));
const pressEnter = (label: string) => fireEvent.keyDown(field(label), { key: 'Enter' });

const statusText = () => panel().getByRole('status').textContent;
const resetButton = () => panel().queryByRole('button', { name: 'Reset to defaults' });

// ------------------------------------------------------------------ schema

describe('BOQ assumptions: schema', () => {
  it('parses a result with assumptions and changes none of them', () => {
    const result = boqResultSchema.parse(RAW_BOQ_RESULT);
    expect(result.assumptions).toEqual(RAW_ASSUMPTIONS); // the key the page does not know included
    expect(result.assumptions?.ceiling_heights_m).toEqual([2.8, 3.1]);
    expect(result.assumptions?.plot_perimeter_m).toBeNull();
  });

  it('parses a result from an older server, which has no assumptions', () => {
    const { assumptions: _dropped, ...older } = RAW_BOQ_RESULT;
    const result = boqResultSchema.parse(older);
    expect(result.assumptions).toBeUndefined();
    expect('assumptions' in result).toBe(false);
    expect(result.items).toHaveLength(RAW_BOQ_RESULT.items.length);
  });

  it('takes values it does not know yet, but not another shape', () => {
    const parses = (change: Record<string, unknown>) =>
      boqResultSchema.safeParse({ ...RAW_BOQ_RESULT, assumptions: { ...RAW_ASSUMPTIONS, ...change } }).success;
    expect(parses({ building_type: 'warehouse', tile_size_mm: '750x750', ceiling_height_source: 'surveyed' })).toBe(true);
    expect(parses({ plot_perimeter_m: 86.5 })).toBe(true);
    expect(parses({ ceiling_heights_m: 3.35 })).toBe(false);
    expect(parses({ false_ceiling_share: '1' })).toBe(false);
    expect(parses({ plot_perimeter_m: undefined })).toBe(false);
  });
});

// ------------------------------------------------------------------- panel

function renderPanel(
  used: Record<string, unknown> = {},
  props: Partial<{ choices: BoqAssumptionsInput; busy: boolean; error: string | null }> = {},
) {
  const onRecalculate = vi.fn<(choices: BoqAssumptionsInput) => void>();
  render(
    <BoqAssumptions
      assumptions={boqAssumptionsSchema.parse({ ...RAW_ASSUMPTIONS, ...used })}
      choices={props.choices ?? {}}
      busy={props.busy ?? false}
      error={props.error ?? null}
      onRecalculate={onRecalculate}
    />,
  );
  return onRecalculate;
}

describe('BoqAssumptions panel', () => {
  it('is a named region whose controls all have a visible label', () => {
    renderPanel();
    expect(panel().getByRole('heading', { name: 'Assumptions' })).toBeDefined();
    expect(panel().getByText(/the drawing is not read again/i)).toBeDefined();
    for (const label of [LABELS.building, LABELS.tileSize, LABELS.tilePattern]) expect(select(label)).toBeDefined();
    for (const label of [LABELS.height, LABELS.falseCeiling, LABELS.perimeter]) {
      expect(field(label).type).toBe('number');
    }
    // the labels are real <label for> elements, not aria-label
    expect(panel().getByText(LABELS.height).tagName).toBe('LABEL');
    expect(panel().getByText(LABELS.height).getAttribute('for')).toBe(field(LABELS.height).id);
  });

  it('shows the values in use and where they come from', () => {
    renderPanel();
    // a building type from the plan that is none of the three is shown as it is
    expect(select(LABELS.building).value).toBe('residential');
    expect(optionsOf(LABELS.building)).toEqual(['Residential', 'Villa', 'Apartment', 'Other']);
    expect(descriptionOf(select(LABELS.building))).toEqual(['From the plan']);

    expect(field(LABELS.height).value).toBe(''); // empty: from the plan
    expect(field(LABELS.height).placeholder).toBe('From the plan');
    expect(descriptionOf(field(LABELS.height))).toEqual(['2.80 m, 3.10 m from the plan']);

    expect(select(LABELS.tileSize).value).toBe('600x600');
    expect(optionsOf(LABELS.tileSize)).toEqual(['600 x 600 mm', '800 x 800 mm', '1200 x 600 mm']);
    expect(select(LABELS.tilePattern).value).toBe('standard');
    expect(optionsOf(LABELS.tilePattern)).toEqual(['Standard (5% waste)', 'Herringbone (15% waste)']);

    expect(field(LABELS.falseCeiling).value).toBe('100');
    expect(field(LABELS.perimeter).value).toBe('');
    expect(descriptionOf(field(LABELS.perimeter))).toEqual(['Estimated from the plan']);

    expect(statusText()).toBe('');
    expect(panel().queryByRole('alert')).toBeNull();
  });

  it.each([
    { heights: [3.35], source: 'assumed', hint: '3.35 m assumed: the plan states none', typed: '' },
    { heights: [3.35, 3.35], source: 'assumed', hint: '3.35 m assumed: the plan states none', typed: '' },
    { heights: [3, 3], source: 'user', hint: '3.00 m on every level, set by you', typed: '3' },
    { heights: [2.75], source: 'user', hint: '2.75 m on every level, set by you', typed: '2.75' },
    {
      heights: [2.8, 3.35],
      source: 'mixed',
      hint: '2.80 m, 3.35 m per level: from the plan where stated, otherwise assumed',
      typed: '',
    },
    { heights: [2.8, 3.1], source: 'surveyed', hint: '2.80 m, 3.10 m', typed: '' }, // a source the page does not know
  ])('describes the ceiling heights in use: $hint', ({ heights, source, hint, typed }) => {
    renderPanel({ ceiling_heights_m: heights, ceiling_height_source: source });
    expect(descriptionOf(field(LABELS.height))).toEqual([hint]);
    expect(field(LABELS.height).value).toBe(typed);
  });

  it('says where the building type comes from', () => {
    renderPanel({ building_type: 'apartment', building_type_source: 'user' });
    expect(select(LABELS.building).value).toBe('apartment');
    expect(optionsOf(LABELS.building)).toEqual(['Villa', 'Apartment', 'Other']);
    expect(descriptionOf(select(LABELS.building))).toEqual(['Set by you']);
  });

  it('says so when the building type is the default', () => {
    renderPanel({ building_type: 'villa', building_type_source: 'default' });
    expect(select(LABELS.building).value).toBe('villa');
    expect(descriptionOf(select(LABELS.building))).toEqual(['Default: the plan states none']);
  });

  it('shows a false-ceiling share as a percentage and a plot perimeter that was set', () => {
    renderPanel({ false_ceiling_share: 0.333, plot_perimeter_m: 86.5, tile_size_mm: '1200x600', tile_pattern: 'herringbone' });
    expect(field(LABELS.falseCeiling).value).toBe('33.3');
    expect(field(LABELS.perimeter).value).toBe('86.5');
    expect(descriptionOf(field(LABELS.perimeter))).toEqual(['Set by you']);
    expect(select(LABELS.tileSize).value).toBe('1200x600');
    expect(select(LABELS.tilePattern).value).toBe('herringbone');
  });

  it('shows a value it has no option for as it is, next to the options', () => {
    renderPanel({ tile_size_mm: '750x750', tile_pattern: 'basketweave' });
    expect(select(LABELS.tileSize).value).toBe('750x750');
    expect(optionsOf(LABELS.tileSize)).toEqual(['750 x 750 mm', '600 x 600 mm', '800 x 800 mm', '1200 x 600 mm']);
    expect(select(LABELS.tilePattern).value).toBe('basketweave');
    expect(optionsOf(LABELS.tilePattern)).toEqual(['Basketweave', 'Standard (5% waste)', 'Herringbone (15% waste)']);
  });

  it('offers "Reset to defaults" only when the person changed something', () => {
    renderPanel({ tile_pattern: 'herringbone' }); // not the default, but not the person's doing either
    expect(resetButton()).toBeNull();
  });

  it('resets with an empty set of choices', () => {
    const onRecalculate = renderPanel({}, { choices: { tile_pattern: 'standard' } });
    const button = resetButton();
    if (!button) throw new Error('no reset button');
    fireEvent.click(button);
    expect(onRecalculate.mock.calls).toEqual([[{}]]);
  });

  it('adds a pick to the choices already made', () => {
    const onRecalculate = renderPanel({}, { choices: { ceiling_height_m: 3, false_ceiling_share: 0.5 } });
    choose(LABELS.building, 'other');
    expect(onRecalculate.mock.calls).toEqual([[{ ceiling_height_m: 3, false_ceiling_share: 0.5, building_type: 'other' }]]);
  });

  it('says it is recalculating and disables every control meanwhile', () => {
    renderPanel({}, { choices: { tile_pattern: 'standard' }, busy: true });
    const status = panel().getByRole('status');
    expect(status.textContent).toBe('Recalculating...');
    expect(status.getAttribute('aria-live')).toBe('polite');
    for (const label of [LABELS.building, LABELS.tileSize, LABELS.tilePattern]) expect(select(label).disabled, label).toBe(true);
    for (const label of [LABELS.height, LABELS.falseCeiling, LABELS.perimeter]) expect(field(label).disabled, label).toBe(true);
    expect(resetButton()?.hasAttribute('disabled')).toBe(true);
  });

  it('shows why a recalculation failed', () => {
    renderPanel({}, { error: 'Could not reach the server.' });
    expect(panel().getByRole('alert').textContent).toBe('Could not reach the server.');
    expect(select(LABELS.building).disabled).toBe(false);
  });
});

// ---------------------------------------------------------------- API + page

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const jobEvent = (stage: string, status: string, progress: number) => ({
  job_id: 'job-1',
  status,
  stage,
  detail: `${stage} the plan`,
  progress,
  error: null,
});

const DONE = [jobEvent('queued', 'queued', 0), jobEvent('parsing', 'running', 40), jobEvent('done', 'done', 100)];

function sse(events: unknown[]): Response {
  const text = events.map((event) => `event: progress\ndata: ${JSON.stringify(event)}\n\n`).join('');
  return new Response(`${text}event: end\ndata: {}\n\n`, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}

/**
 * What the server answers to a recalculation: the bill with other quantities (here: the
 * bricks) and the assumptions that were used, the way the calculator reports them.
 */
function billFor(choices: BoqAssumptionsInput, bricks = 9999) {
  const height = choices.ceiling_height_m ?? null;
  return {
    ...RAW_BOQ_RESULT,
    items: RAW_BOQ_RESULT.items.map((item) => (item.item_code === 'bricks' ? { ...item, quantity: bricks } : item)),
    assumptions: {
      ...RAW_ASSUMPTIONS,
      building_type: choices.building_type ?? RAW_ASSUMPTIONS.building_type,
      building_type_source: choices.building_type ? 'user' : RAW_ASSUMPTIONS.building_type_source,
      ceiling_heights_m:
        height === null ? RAW_ASSUMPTIONS.ceiling_heights_m : RAW_ASSUMPTIONS.ceiling_heights_m.map(() => height),
      ceiling_height_source: height === null ? RAW_ASSUMPTIONS.ceiling_height_source : 'user',
      tile_size_mm: choices.tile_size_mm ?? '600x600',
      tile_pattern: choices.tile_pattern ?? 'standard',
      false_ceiling_share: choices.false_ceiling_share ?? 1,
      plot_perimeter_m: choices.plot_perimeter_m ?? null,
    },
  };
}

interface MockApi {
  /** The bill the job ends with; without it, the fixture. */
  result?: unknown;
  /** The answer to a recalculation; without it, the bill for the choices in the request. */
  recalculate?: (choices: BoqAssumptionsInput) => Response | Promise<Response>;
}

function mockApi(api: MockApi = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith(BOQ_BASE) && init?.method === 'POST') return json({ job_id: 'job-1' }, 202);
    if (url.endsWith('/jobs/job-1/events')) return sse(DONE);
    if (url.endsWith('/jobs/job-1/result')) return json(api.result ?? RAW_BOQ_RESULT);
    if (url.endsWith(RECALCULATE) && init?.method === 'POST') {
      const choices: BoqAssumptionsInput = JSON.parse(String(init.body));
      return api.recalculate ? api.recalculate(choices) : json(billFor(choices));
    }
    if (url.includes(`${BOQ_BASE}/export/`)) {
      return new Response('%PDF-1.7', { status: 200, headers: { 'Content-Type': 'application/pdf' } });
    }
    return json({ detail: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

type FetchMock = ReturnType<typeof mockApi>;

/** The recalculation requests so far, oldest first. */
const recalculations = (fetchMock: FetchMock) =>
  fetchMock.mock.calls
    .filter(([input]) => String(input).endsWith(RECALCULATE))
    .map(([input, init]) => ({ url: String(input), init: init ?? {}, body: JSON.parse(String(init?.body)) as unknown }));

const bodies = (fetchMock: FetchMock) => recalculations(fetchMock).map((request) => request.body);

const pdf = () => new File(['%PDF-1.7'], 'green-villa.pdf', { type: 'application/pdf' });

function upload() {
  fireEvent.change(screen.getByLabelText('Floor plan PDF'), { target: { files: [pdf()] } });
  fireEvent.click(screen.getByRole('button', { name: 'Generate BOQ' }));
  return screen.findByRole('heading', { name: 'Green Villa' });
}

async function generate() {
  render(
    <MemoryRouter>
      <BoqPage />
    </MemoryRouter>,
  );
  await upload();
}

/** The quantity shown in the bill for one material. */
const quantityOf = (name: string) => screen.getByText(name).closest('tr')?.children[5].firstChild?.textContent;

/** Wait until the recalculation in flight is over. */
const settled = () => waitFor(() => expect(statusText()).toBe(''));

/** A reply the test sends when it chooses to. */
function deferredReplies() {
  const send: Array<(reply: Response) => void> = [];
  const recalculate = () => new Promise<Response>((resolve) => send.push(resolve));
  return { send, recalculate };
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem(TOKEN_STORAGE_KEY, 'test-jwt-token');
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('BOQ page: assumptions', () => {
  it('shows the panel between the summary and the table once the bill is ready', async () => {
    mockApi();
    render(
      <MemoryRouter>
        <BoqPage />
      </MemoryRouter>,
    );
    expect(screen.queryByRole('region', { name: 'Assumptions' })).toBeNull();
    await upload();

    const region = screen.getByRole('region', { name: 'Assumptions' });
    const before = (other: HTMLElement) => Boolean(region.compareDocumentPosition(other) & Node.DOCUMENT_POSITION_FOLLOWING);
    expect(before(screen.getByRole('region', { name: 'Plan summary' }))).toBe(false);
    expect(before(screen.getByRole('table', { name: /bill of quantities/i }))).toBe(true);
    expect(descriptionOf(field(LABELS.height))).toEqual(['2.80 m, 3.10 m from the plan']);
    expect(resetButton()).toBeNull();
  });

  it('recalculates at once when a select changes, then shows the bill that came back', async () => {
    const replies = deferredReplies();
    const fetchMock = mockApi({ recalculate: replies.recalculate });
    await generate();
    expect(quantityOf('Bricks')).toBe('12,480');

    choose(LABELS.tileSize, '800x800');

    // in flight: a polite status, every control disabled, and no download of the old bill
    expect(statusText()).toBe('Recalculating...');
    expect(select(LABELS.tileSize).value).toBe('800x800');
    expect(select(LABELS.tileSize).disabled).toBe(true);
    expect(field(LABELS.height).disabled).toBe(true);
    expect(screen.getByRole('button', { name: 'Download PDF' }).hasAttribute('disabled')).toBe(true);
    expect(screen.getByRole('button', { name: 'Download Excel' }).hasAttribute('disabled')).toBe(true);
    expect(quantityOf('Bricks')).toBe('12,480');

    await waitFor(() => expect(replies.send).toHaveLength(1));
    const requests = recalculations(fetchMock);
    expect(requests).toHaveLength(1);
    expect(requests[0].url).toBe(`http://localhost:8000${BOQ_BASE}${RECALCULATE}`);
    expect(requests[0].init.method).toBe('POST');
    const headers = new Headers(requests[0].init.headers);
    expect(headers.get('Authorization')).toBe('Bearer test-jwt-token');
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(requests[0].body).toEqual({ tile_size_mm: '800x800' }); // only what the person chose

    replies.send[0](
      json({
        ...billFor({ tile_size_mm: '800x800' }),
        warnings: ['Large tiles: check the cutting waste on site.'],
        geometry_summary: { ...RAW_BOQ_RESULT.geometry_summary, rooms_count: 15 },
      }),
    );

    // the table, the summary, the warnings and the panel all show the new bill
    await waitFor(() => expect(quantityOf('Bricks')).toBe('9,999'));
    const summary = within(screen.getByRole('region', { name: 'Plan summary' }));
    expect(summary.getByText('Rooms').parentElement?.textContent).toBe('Rooms15');
    const warnings = within(screen.getByRole('region', { name: 'Warnings' }));
    expect(warnings.getByRole('heading', { name: '1 warning' })).toBeDefined();
    expect(warnings.getByText(/large tiles/i)).toBeDefined();
    expect(statusText()).toBe('');
    expect(select(LABELS.tileSize).value).toBe('800x800');
    expect(select(LABELS.tileSize).disabled).toBe(false);
    expect(field(LABELS.height).disabled).toBe(false);
    expect(screen.getByRole('button', { name: 'Download PDF' }).hasAttribute('disabled')).toBe(false);
    expect(resetButton()).not.toBeNull();
    expect(recalculations(fetchMock)).toHaveLength(1);
  });

  it('sends every choice so far with each change, and {} on "Reset to defaults"', async () => {
    const fetchMock = mockApi();
    await generate();

    choose(LABELS.tileSize, '1200x600');
    await settled();
    choose(LABELS.building, 'apartment');
    await settled();
    choose(LABELS.tilePattern, 'herringbone');
    await settled();
    expect(bodies(fetchMock)).toEqual([
      { tile_size_mm: '1200x600' },
      { tile_size_mm: '1200x600', building_type: 'apartment' },
      { tile_size_mm: '1200x600', building_type: 'apartment', tile_pattern: 'herringbone' },
    ]);
    expect(select(LABELS.building).value).toBe('apartment');
    expect(optionsOf(LABELS.building)).toEqual(['Villa', 'Apartment', 'Other']);
    expect(descriptionOf(select(LABELS.building))).toEqual(['Set by you']);

    const button = resetButton();
    if (!button) throw new Error('no reset button');
    button.focus();
    fireEvent.click(button);
    expect(statusText()).toBe('Recalculating...');
    await settled();
    expect(bodies(fetchMock)).toHaveLength(4);
    expect(bodies(fetchMock)[3]).toEqual({});

    // back to what the plan says, and nothing left to reset
    expect(select(LABELS.building).value).toBe('residential');
    expect(select(LABELS.tileSize).value).toBe('600x600');
    expect(select(LABELS.tilePattern).value).toBe('standard');
    expect(resetButton()).toBeNull();
    // the button is gone: the keyboard focus goes to the first control, not nowhere
    expect(document.activeElement).toBe(select(LABELS.building));
  });

  it('sends a number when its field is left', async () => {
    const fetchMock = mockApi();
    await generate();
    typeIn(LABELS.height, '3');
    expect(recalculations(fetchMock)).toHaveLength(0); // not while typing
    leave(LABELS.height);
    expect(statusText()).toBe('Recalculating...');
    expect(field(LABELS.height).value).toBe('3');
    await settled();

    expect(bodies(fetchMock)).toEqual([{ ceiling_height_m: 3 }]);
    expect(field(LABELS.height).value).toBe('3');
    expect(descriptionOf(field(LABELS.height))).toEqual(['3.00 m on every level, set by you']);
    expect(quantityOf('Bricks')).toBe('9,999');
  });

  it('sends a number on Enter, and only once', async () => {
    const fetchMock = mockApi();
    await generate();
    typeIn(LABELS.perimeter, '86.5');
    pressEnter(LABELS.perimeter);
    leave(LABELS.perimeter); // the field is left while the request is in flight
    await settled();
    leave(LABELS.perimeter); // and again afterwards
    pressEnter(LABELS.perimeter);

    expect(bodies(fetchMock)).toEqual([{ plot_perimeter_m: 86.5 }]);
    expect(field(LABELS.perimeter).value).toBe('86.5');
    expect(descriptionOf(field(LABELS.perimeter))).toEqual(['Set by you']);
    expect(statusText()).toBe('');
  });

  it('sends nothing for a number that did not change', async () => {
    const fetchMock = mockApi();
    await generate();
    leave(LABELS.height); // never typed in
    pressEnter(LABELS.falseCeiling);
    typeIn(LABELS.falseCeiling, '100.0'); // the same 100%
    leave(LABELS.falseCeiling);
    typeIn(LABELS.height, '3');
    typeIn(LABELS.height, ''); // typed, then emptied again: still "from the plan"
    pressEnter(LABELS.height);
    leave(LABELS.height);

    expect(recalculations(fetchMock)).toHaveLength(0);
    expect(statusText()).toBe('');
    expect(field(LABELS.falseCeiling).value).toBe('100');
    expect(panel().queryByRole('alert')).toBeNull();
    expect(resetButton()).toBeNull();
  });

  it('sends the false ceiling as a share of 1', async () => {
    const fetchMock = mockApi();
    await generate();
    typeIn(LABELS.falseCeiling, '50');
    leave(LABELS.falseCeiling);
    await settled();
    expect(field(LABELS.falseCeiling).value).toBe('50');

    typeIn(LABELS.falseCeiling, '33.3');
    pressEnter(LABELS.falseCeiling);
    await settled();
    typeIn(LABELS.falseCeiling, '0');
    pressEnter(LABELS.falseCeiling);
    await settled();

    expect(bodies(fetchMock)).toEqual([{ false_ceiling_share: 0.5 }, { false_ceiling_share: 0.333 }, { false_ceiling_share: 0 }]);
    expect(field(LABELS.falseCeiling).value).toBe('0');
  });

  it('leaves an emptied ceiling height out of the request, keeping the other choices', async () => {
    const fetchMock = mockApi();
    await generate();
    choose(LABELS.tilePattern, 'herringbone');
    await settled();
    typeIn(LABELS.height, '2.75');
    leave(LABELS.height);
    await settled();
    expect(descriptionOf(field(LABELS.height))).toEqual(['2.75 m on every level, set by you']);

    typeIn(LABELS.height, '');
    leave(LABELS.height);
    await settled();

    expect(bodies(fetchMock)).toEqual([
      { tile_pattern: 'herringbone' },
      { tile_pattern: 'herringbone', ceiling_height_m: 2.75 },
      { tile_pattern: 'herringbone' },
    ]);
    expect(Object.keys(Object(bodies(fetchMock)[2]))).toEqual(['tile_pattern']); // left out, not null
    expect(field(LABELS.height).value).toBe('');
    expect(descriptionOf(field(LABELS.height))).toEqual(['2.80 m, 3.10 m from the plan']);
    expect(select(LABELS.tilePattern).value).toBe('herringbone');
  });

  it.each([
    { name: 'a ceiling height of 1.99', label: LABELS.height, text: '1.99', message: /from 2 to 8 m/ },
    { name: 'a ceiling height of 8.01', label: LABELS.height, text: '8.01', message: /from 2 to 8 m/ },
    { name: 'a false ceiling of -1', label: LABELS.falseCeiling, text: '-1', message: /percentage from 0 to 100/ },
    { name: 'a false ceiling of 100.5', label: LABELS.falseCeiling, text: '100.5', message: /percentage from 0 to 100/ },
    { name: 'an empty false ceiling', label: LABELS.falseCeiling, text: '', message: /percentage from 0 to 100/ },
    { name: 'a plot perimeter of 0', label: LABELS.perimeter, text: '0', message: /perimeter above 0 m/ },
    { name: 'a plot perimeter of -12', label: LABELS.perimeter, text: '-12', message: /perimeter above 0 m/ },
    { name: 'a plot perimeter of 100001', label: LABELS.perimeter, text: '100001', message: /perimeter above 0 m/ },
  ])('refuses $name with a message next to the field, and sends nothing', async ({ label, text, message }) => {
    const fetchMock = mockApi();
    await generate();
    const hint = descriptionOf(field(label));
    typeIn(label, text);
    expect(field(label).getAttribute('aria-invalid')).toBeNull(); // not while typing
    leave(label);

    const problem = panel().getByRole('alert');
    expect(problem.textContent).toMatch(message);
    expect(field(label).getAttribute('aria-invalid')).toBe('true');
    expect(descriptionOf(field(label))).toEqual([...hint, problem.textContent]);
    expect(problem.closest('div')?.contains(field(label))).toBe(true); // in the field's own block
    expect(field(label).value).toBe(text);
    pressEnter(label);
    expect(recalculations(fetchMock)).toHaveLength(0);
    expect(statusText()).toBe('');

    // typing again takes the message away; a valid number is then sent
    typeIn(label, '5');
    expect(panel().queryByRole('alert')).toBeNull();
    expect(field(label).getAttribute('aria-invalid')).toBeNull();
    pressEnter(label);
    await settled();
    expect(recalculations(fetchMock)).toHaveLength(1);
    expect(field(label).value).toBe('5');
  });

  it('keeps a refused number next to its message while another change is applied', async () => {
    const fetchMock = mockApi();
    await generate();
    typeIn(LABELS.height, '9');
    leave(LABELS.height);
    choose(LABELS.tileSize, '800x800');
    await settled();

    expect(bodies(fetchMock)).toEqual([{ tile_size_mm: '800x800' }]); // the refused height is not sent along
    expect(field(LABELS.height).value).toBe('9');
    expect(panel().getByRole('alert').textContent).toMatch(/from 2 to 8 m/);

    // "Reset to defaults" clears it with everything else
    const button = resetButton();
    if (!button) throw new Error('no reset button');
    fireEvent.click(button);
    await settled();
    expect(field(LABELS.height).value).toBe('');
    expect(panel().queryByRole('alert')).toBeNull();
    expect(bodies(fetchMock)[1]).toEqual({});
  });

  it.each([
    {
      name: 'a bill that has expired (404)',
      reply: () => json({ detail: 'BOQ job not found' }, 404),
      message: 'This bill has expired. Upload the plan again to change its assumptions.',
    },
    {
      name: "the server's own message (422)",
      reply: () => json({ detail: 'Quantities could not be calculated: the plan has no rooms.' }, 422),
      message: 'Quantities could not be calculated: the plan has no rooms.',
    },
    {
      name: 'a list of validation issues (422)',
      reply: () =>
        json(
          {
            detail: [
              { type: 'less_than_equal', loc: ['body', 'ceiling_height_m'], msg: 'Input should be less than or equal to 8', input: 9 },
              { type: 'extra_forbidden', loc: ['body', 'colour'], msg: 'Extra inputs are not permitted', input: 'red' },
            ],
          },
          422,
        ),
      message: 'ceiling_height_m: Input should be less than or equal to 8 colour: Extra inputs are not permitted',
    },
    {
      name: 'a job that is not done (409)',
      reply: () => json({ detail: 'The BOQ is not ready yet.' }, 409),
      message: 'The BOQ is not ready yet.',
    },
    {
      name: 'an error without a readable body (500)',
      reply: () => new Response('<html>Bad gateway</html>', { status: 500 }),
      message: 'Request failed with status 500',
    },
    {
      name: 'a network error',
      reply: (): Response => {
        throw new TypeError('Failed to fetch');
      },
      message: 'Could not reach the server. Check your connection and try again.',
    },
    {
      name: 'an answer that is not a bill',
      reply: () => json({ items: 'none' }),
      message: 'The server sent a result this page could not read. Please try again.',
    },
  ])('shows $name in the panel and keeps the bill on screen', async ({ reply, message }) => {
    let failing = true;
    const fetchMock = mockApi({ recalculate: (choices) => (failing ? reply() : json(billFor(choices))) });
    await generate();
    choose(LABELS.tileSize, '800x800');

    const alert = await panel().findByRole('alert');
    expect(alert.textContent).toBe(message);
    expect(statusText()).toBe('');
    // the bill, and the panel that describes it, are as they were
    expect(quantityOf('Bricks')).toBe('12,480');
    expect(screen.getByRole('table', { name: /bill of quantities/i })).toBeDefined();
    expect(select(LABELS.tileSize).value).toBe('600x600');
    expect(select(LABELS.tileSize).disabled).toBe(false);
    expect(resetButton()).toBeNull();
    expect(screen.getByRole('button', { name: 'Download PDF' }).hasAttribute('disabled')).toBe(false);

    // trying again works, sends only that choice and takes the message away
    failing = false;
    choose(LABELS.tileSize, '800x800');
    expect(panel().queryByRole('alert')).toBeNull();
    await waitFor(() => expect(quantityOf('Bricks')).toBe('9,999'));
    expect(bodies(fetchMock)).toEqual([{ tile_size_mm: '800x800' }, { tile_size_mm: '800x800' }]);
    expect(panel().queryByRole('alert')).toBeNull();
    expect(select(LABELS.tileSize).value).toBe('800x800');
  });

  it('does not leave a number in its field when it could not be applied', async () => {
    const fetchMock = mockApi({ recalculate: () => json({ detail: 'BOQ job not found' }, 404) });
    await generate();
    typeIn(LABELS.height, '3');
    pressEnter(LABELS.height);
    expect((await panel().findByRole('alert')).textContent).toMatch(/expired.*upload the plan again/i);

    // the field shows what the bill on screen uses, and leaving it does not try again
    expect(field(LABELS.height).value).toBe('');
    expect(descriptionOf(field(LABELS.height))).toEqual(['2.80 m, 3.10 m from the plan']);
    leave(LABELS.height);
    expect(recalculations(fetchMock)).toHaveLength(1);
    expect(statusText()).toBe('');
  });

  it('exports the bill on screen: after a recalculation, the new rows and assumptions', async () => {
    const fetchMock = mockApi();
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, writable: true, value: vi.fn(() => 'blob:boq') });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, writable: true, value: vi.fn() });
    await generate();
    choose(LABELS.tilePattern, 'herringbone');
    await settled();
    typeIn(LABELS.falseCeiling, '40');
    pressEnter(LABELS.falseCeiling);
    await settled();

    fireEvent.click(screen.getByRole('button', { name: 'Download Excel' }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith('/export/xlsx'))).toBe(true));
    const request = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/export/xlsx'));
    const body: unknown = JSON.parse(String(request?.[1]?.body));
    const bill = billFor({ tile_pattern: 'herringbone', false_ceiling_share: 0.4 });
    expect(body).toEqual({
      items: bill.items,
      warnings: bill.warnings,
      geometry_summary: bill.geometry_summary,
      project_metadata: bill.project_metadata,
      assumptions: bill.assumptions, // as the server sent them, the unknown key included
    });
    expect(bill.assumptions).toMatchObject({ tile_pattern: 'herringbone', false_ceiling_share: 0.4, skirting_height_mm: 100 });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Download Excel' }).hasAttribute('disabled')).toBe(false));
  });

  it('starts a new plan without the choices made for the one before', async () => {
    const fetchMock = mockApi();
    await generate();
    choose(LABELS.tileSize, '800x800');
    await settled();
    expect(resetButton()).not.toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Upload another plan' }));
    expect(screen.queryByRole('region', { name: 'Assumptions' })).toBeNull();
    await upload();
    expect(resetButton()).toBeNull();
    expect(select(LABELS.tileSize).value).toBe('600x600');

    choose(LABELS.tilePattern, 'herringbone');
    await settled();
    expect(bodies(fetchMock)).toEqual([{ tile_size_mm: '800x800' }, { tile_pattern: 'herringbone' }]);
  });

  it('has no panel for a bill from an older server, which reports no assumptions', async () => {
    const { assumptions: _dropped, ...older } = RAW_BOQ_RESULT;
    mockApi({ result: older });
    await generate();
    expect(screen.getByText('Bricks')).toBeDefined();
    expect(screen.queryByRole('region', { name: 'Assumptions' })).toBeNull();
  });
});

// ------------------------------------------------------------------- hook

describe('useBoqJob: recalculation', () => {
  const bricksOf = (bill: BoqResult | null) => bill?.items.find((item) => item.item_code === 'bricks')?.quantity;

  /** Let a reply that was just sent be read and handled (or ignored). */
  const handled = async (reply: Response) => {
    await waitFor(() => expect(reply.bodyUsed).toBe(true));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
  };

  async function readyJob() {
    const hook = renderHook(() => useBoqJob());
    act(() => {
      void hook.result.current.start(pdf());
    });
    await waitFor(() => expect(hook.result.current.phase).toBe('ready'));
    return hook.result;
  }

  it.each([
    { name: 'after the newer one', order: ['newer', 'older'] as const },
    { name: 'before the newer one', order: ['older', 'newer'] as const },
  ])('ignores the reply to an older request that arrives $name', async ({ order }) => {
    const replies = deferredReplies();
    const fetchMock = mockApi({ recalculate: replies.recalculate });
    const job = await readyJob();
    expect(bricksOf(job.current.result)).toBe(12480);

    act(() => {
      void job.current.recalculate({ tile_size_mm: '800x800' });
    });
    await waitFor(() => expect(replies.send).toHaveLength(1));
    act(() => {
      void job.current.recalculate({ tile_size_mm: '800x800', tile_pattern: 'herringbone' });
    });
    await waitFor(() => expect(replies.send).toHaveLength(2));
    // the older request is aborted, so a real network stops working on it
    expect(recalculations(fetchMock).map((request) => request.init.signal?.aborted)).toEqual([true, false]);

    const older = json(billFor({ tile_size_mm: '800x800' }, 111));
    const newer = json(billFor({ tile_size_mm: '800x800', tile_pattern: 'herringbone' }, 222));
    for (const which of order) {
      if (which === 'older') {
        replies.send[0](older);
        await handled(older);
        // whenever it arrives, it changes nothing
        expect(bricksOf(job.current.result)).toBe(order[0] === 'older' ? 12480 : 222);
        expect(job.current.recalculating).toBe(order[0] === 'older');
      } else {
        replies.send[1](newer);
        await waitFor(() => expect(job.current.recalculating).toBe(false));
        expect(bricksOf(job.current.result)).toBe(222);
      }
    }

    expect(bricksOf(job.current.result)).toBe(222);
    expect(job.current.result?.assumptions?.tile_pattern).toBe('herringbone');
    expect(job.current.assumptionsInput).toEqual({ tile_size_mm: '800x800', tile_pattern: 'herringbone' });
    expect(job.current.recalculating).toBe(false);
    expect(job.current.recalculateError).toBeNull();
    expect(job.current.phase).toBe('ready');
  });

  it('keeps the bill and the choices behind it when a recalculation fails', async () => {
    let failing = false;
    mockApi({ recalculate: (choices) => (failing ? json({ detail: 'The calculator is busy.' }, 503) : json(billFor(choices, 111))) });
    const job = await readyJob();
    expect(job.current.assumptionsInput).toEqual({});

    await act(() => job.current.recalculate({ building_type: 'villa' }));
    expect(bricksOf(job.current.result)).toBe(111);
    expect(job.current.assumptionsInput).toEqual({ building_type: 'villa' });

    failing = true;
    await act(() => job.current.recalculate({ building_type: 'villa', ceiling_height_m: 3 }));
    expect(job.current.recalculateError).toBe('The calculator is busy.');
    expect(job.current.recalculating).toBe(false);
    expect(job.current.phase).toBe('ready');
    expect(bricksOf(job.current.result)).toBe(111);
    expect(job.current.result?.assumptions?.building_type_source).toBe('user');
    expect(job.current.assumptionsInput).toEqual({ building_type: 'villa' });

    failing = false;
    await act(() => job.current.recalculate({ building_type: 'villa', ceiling_height_m: 3 }));
    expect(job.current.recalculateError).toBeNull();
    expect(job.current.assumptionsInput).toEqual({ building_type: 'villa', ceiling_height_m: 3 });
  });

  it('drops a recalculation in flight, its error and the choices on reset', async () => {
    const replies = deferredReplies();
    let failing = true;
    mockApi({ recalculate: () => (failing ? json({ detail: 'No.' }, 500) : replies.recalculate()) });
    const job = await readyJob();
    await act(() => job.current.recalculate({ tile_size_mm: '800x800' }));
    expect(job.current.recalculateError).toBe('No.');

    failing = false;
    act(() => {
      void job.current.recalculate({ tile_size_mm: '800x800' });
    });
    await waitFor(() => expect(replies.send).toHaveLength(1));
    expect(job.current.recalculating).toBe(true);
    expect(job.current.recalculateError).toBeNull();

    act(() => job.current.reset());
    expect(job.current.phase).toBe('idle');
    expect(job.current.recalculating).toBe(false);

    const late = json(billFor({ tile_size_mm: '800x800' }, 111));
    replies.send[0](late);
    await handled(late);
    expect(job.current.phase).toBe('idle');
    expect(job.current.result).toBeNull();
    expect(job.current.recalculating).toBe(false);
    expect(job.current.recalculateError).toBeNull();
    expect(job.current.assumptionsInput).toEqual({});
  });

  it('starts another upload without the choices or the recalculation of the bill before', async () => {
    const replies = deferredReplies();
    let held = false;
    mockApi({ recalculate: (choices) => (held ? replies.recalculate() : json(billFor(choices, 111))) });
    const job = await readyJob();
    await act(() => job.current.recalculate({ tile_size_mm: '800x800' }));
    expect(job.current.assumptionsInput).toEqual({ tile_size_mm: '800x800' });

    held = true;
    act(() => {
      void job.current.recalculate({ tile_size_mm: '800x800', tile_pattern: 'herringbone' });
    });
    await waitFor(() => expect(replies.send).toHaveLength(1));

    // straight to another upload, without a reset in between
    act(() => {
      void job.current.start(pdf());
    });
    expect(job.current.recalculating).toBe(false);
    expect(job.current.assumptionsInput).toEqual({});
    await waitFor(() => expect(job.current.phase).toBe('ready'));

    const late = json(billFor({ tile_size_mm: '800x800', tile_pattern: 'herringbone' }, 222));
    replies.send[0](late);
    await handled(late);
    expect(bricksOf(job.current.result)).toBe(12480); // the new upload's own bill
    expect(job.current.assumptionsInput).toEqual({});
    expect(job.current.recalculating).toBe(false);
  });

  it('does nothing before there is a bill', async () => {
    const fetchMock = mockApi();
    const { result: job } = renderHook(() => useBoqJob());
    await act(() => job.current.recalculate({ tile_size_mm: '800x800' }));
    expect(recalculations(fetchMock)).toHaveLength(0);
    expect(job.current.phase).toBe('idle');
    expect(job.current.recalculating).toBe(false);
  });
});
