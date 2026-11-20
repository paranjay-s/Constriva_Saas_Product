import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TOKEN_STORAGE_KEY } from '../../lib/api';
import { BoqPage } from './BoqPage';
import { BOQ_BASE, boqApi, boqExportBody } from './boqApi';
import { RAW_BOQ_RESULT } from './boqFixture';
import { boqResultSchema } from './boqSchemas';
import { BoqTable } from './components/BoqTable';

const RESULT = boqResultSchema.parse(RAW_BOQ_RESULT);
const TOTAL = RAW_BOQ_RESULT.items.length;

// ------------------------------------------------------------------ schemas

describe('BOQ schemas', () => {
  it('parses a result with lettered, excluded and allowance rows', () => {
    expect(RESULT.items).toHaveLength(TOTAL);
    const find = (code: string) => RESULT.items.find((item) => item.item_code === code);
    expect(find('interior_primer')?.serial_no).toBe('17a');
    expect(find('interior_paint')?.serial_no).toBe(17);
    expect(find('driveway_paving')?.quote_status).toBe('EXCLUDED_FROM_QUOTE');
    expect(find('switches_sockets')?.calc_type).toBe('allowance');
    expect(find('site_barricading')).toMatchObject({ calc_type: 'allowance', quote_status: 'EXCLUDED_FROM_QUOTE' });
    expect(find('bricks')?.components).toHaveLength(3);
    expect(RESULT.warnings).toHaveLength(4);
    expect(RESULT.geometry_summary.a_built_total_m2).toBe(1234.5);
    expect(RESULT.project_metadata.subject).toBeNull();
  });

  it('changes nothing in the rows and loose objects, and drops the older top-level keys', () => {
    expect(RESULT.items).toEqual(RAW_BOQ_RESULT.items); // extra row keys (id, details...) included
    expect(RESULT.geometry_summary).toEqual(RAW_BOQ_RESULT.geometry_summary);
    expect(RESULT.project_metadata).toEqual(RAW_BOQ_RESULT.project_metadata);
    expect(RESULT.assumptions).toEqual(RAW_BOQ_RESULT.assumptions);
    expect(Object.keys(RESULT).sort()).toEqual(['assumptions', 'geometry_summary', 'items', 'project_metadata', 'warnings']);
  });

  it('accepts a bill of any size, with or without the optional fields', () => {
    const minimal = {
      items: [
        {
          serial_no: '59z',
          item_code: 'x',
          category: 'Anything',
          sub_category: '',
          name: 'A new row',
          unit: 'nos',
          quantity: 1,
          components: [],
          calc_type: 'count',
          quote_status: 'INCLUDED',
          note: '',
        },
      ],
      warnings: [],
      geometry_summary: { a_built_total_m2: 0, levels_count: 0, rooms_count: 0, bathrooms_count: 0 },
      project_metadata: {},
    };
    expect(boqResultSchema.safeParse(minimal).success).toBe(true);
    expect(boqResultSchema.safeParse({ ...minimal, items: [] }).success).toBe(true);
    expect(boqResultSchema.safeParse({ ...minimal, items: [{ ...minimal.items[0], category_code: null, quantity_decimals: null }] }).success).toBe(true);
  });

  it('refuses a result that breaks the contract', () => {
    const [first] = RAW_BOQ_RESULT.items;
    const withRow = (row: Record<string, unknown>) => boqResultSchema.safeParse({ ...RAW_BOQ_RESULT, items: [row] }).success;
    expect(withRow({ ...first, quote_status: 'MAYBE' })).toBe(false);
    expect(withRow({ ...first, calc_type: 'guess' })).toBe(false);
    expect(withRow({ ...first, quantity: '12' })).toBe(false);
    expect(boqResultSchema.safeParse({ items: [] }).success).toBe(false);
  });
});

// ------------------------------------------------------------------- table

/** Serial numbers of the item rows inside one category group, top to bottom. */
function serialsOf(group: HTMLTableSectionElement): string[] {
  return Array.from(group.rows)
    .filter((row) => row.cells[0]?.tagName === 'TD' && row.cells.length > 1)
    .map((row) => row.cells[0].textContent ?? '');
}

function subHeadersOf(group: HTMLTableSectionElement): string[] {
  return Array.from(group.querySelectorAll('th[scope="colgroup"]')).map((th) => th.textContent ?? '');
}

function renderTable() {
  render(<BoqTable items={RESULT.items} />);
  const table = screen.getByRole('table', { name: /bill of quantities/i });
  if (!(table instanceof HTMLTableElement)) throw new Error('the bill is not a <table>');
  return table;
}

const rowOf = (name: string): HTMLElement => {
  const row = screen.getByText(name).closest('tr');
  if (!row) throw new Error(`no row for ${name}`);
  return row;
};

describe('BoqTable', () => {
  it('groups the rows by category, with row counts and sub-category subheaders', () => {
    const table = renderTable();
    expect(Array.from(table.tHead?.rows[0].cells ?? []).map((th) => th.textContent?.replace(/[▲▼↕]/g, ''))).toEqual([
      'S.No',
      'Category',
      'Sub-category',
      'Material',
      'Unit',
      'Quantity',
      'Status',
    ]);
    expect(table.tBodies).toHaveLength(6);
    expect(screen.getByRole('button', { name: /A · Structure and Masonry.*3 items/ })).toBeDefined();
    expect(screen.getByRole('button', { name: /B · Civil, Finishing and Waterproofing.*5 items/ })).toBeDefined();
    expect(screen.getByRole('button', { name: /F · Site Setup.*1 item$/ })).toBeDefined();
    expect(subHeadersOf(table.tBodies[1])).toEqual(['Painting', 'Ceilings', 'External works']);
    expect(serialsOf(table.tBodies[1])).toEqual(['17', '17a', '17b', '18', '22']);
    expect(serialsOf(table.tBodies[0])).toEqual(['1', '2', '3']);
  });

  it('right-aligns formatted numbers: whole counts, 2 decimals for measures', () => {
    renderTable();
    // cells: S.No, Category, Sub-category, Material, Unit, Quantity, Status
    const unit = (name: string) => rowOf(name).children[4].textContent;
    const quantity = (name: string) => rowOf(name).children[5];
    expect(unit('Bricks')).toBe('nos');
    expect(quantity('Bricks').firstChild?.textContent).toBe('12,480');
    expect(quantity('Bricks').className).toContain('text-right');
    expect(unit('Gypsum false ceiling')).toBe('m²');
    expect(quantity('Gypsum false ceiling').firstChild?.textContent).toBe('1,234.50');
    expect(quantity('Interior emulsion paint').firstChild?.textContent).toBe('86.40'); // no quantity_decimals: the unit decides
    expect(quantity('Cement').firstChild?.textContent).toBe('412');
    // on narrow screens the unit is repeated under the quantity (the Unit column is hidden there)
    expect(quantity('Cement').textContent).toBe('412bags (50 kg)');
  });

  it('collapses and expands a category group', () => {
    renderTable();
    const header = screen.getByRole('button', { name: /B · Civil, Finishing/ });
    expect(header.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByText('Interior primer')).toBeDefined();

    fireEvent.click(header);
    expect(header.getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByText('Interior primer')).toBeNull();
    expect(screen.getByText('Bricks')).toBeDefined(); // other groups stay open

    fireEvent.click(header);
    expect(screen.getByText('Interior primer')).toBeDefined();

    fireEvent.click(screen.getByRole('button', { name: 'Collapse all' }));
    expect(screen.queryByText('Bricks')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Expand all' }));
    expect(screen.getByText('Bricks')).toBeDefined();
  });

  it('expands a row to show its components and note', () => {
    renderTable();
    const toggle = screen.getByRole('button', { name: /^Bricks/ });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByText('Brickwork volume')).toBeNull();

    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    const parts = screen.getByRole('table', { name: 'Components of Bricks' });
    const cells = (label: string) =>
      Array.from(within(parts).getByText(label).closest('tr')?.cells ?? []).map((cell) => cell.textContent);
    expect(cells('Brickwork volume')).toEqual(['Brickwork volume', '28.60', 'm³']);
    expect(cells('Mortar joints')).toEqual(['Mortar joints', '6,250.00', 'kg']);
    expect(cells('Wall panels')).toEqual(['Wall panels', '42', 'nos']);
    expect(screen.getByText(/includes 5% waste for cutting and breakage/i)).toBeDefined();
    const detail = document.getElementById(toggle.getAttribute('aria-controls') ?? '');
    expect(detail?.contains(parts)).toBe(true);

    fireEvent.click(toggle);
    expect(screen.queryByText('Brickwork volume')).toBeNull();

    // a row with nothing to show has no expand button
    expect(screen.queryByRole('button', { name: /^Steel reinforcement/ })).toBeNull();
    // a note alone is enough
    fireEvent.click(screen.getByRole('button', { name: /^Driveway paving/ }));
    expect(screen.getByText('Outside the building quote.')).toBeDefined();
  });

  it('shows Excluded and Allowance badges, otherwise Included', () => {
    renderTable();
    const badges = (name: string) => {
      const cells = Array.from(rowOf(name).children);
      return Array.from(cells[cells.length - 1].querySelectorAll('span > span')).map((badge) => badge.textContent);
    };
    expect(badges('Bricks')).toEqual(['Included']);
    expect(badges('Driveway paving')).toEqual(['Excluded']);
    expect(badges('Switches and sockets')).toEqual(['Allowance']);
    expect(badges('Site barricading')).toEqual(['Excluded', 'Allowance']);
  });

  it('filters by search, category and status, and clears the filters', () => {
    const table = renderTable();
    expect(screen.getByText(`${TOTAL} items`)).toBeDefined();
    const options = Array.from(screen.getByLabelText('Category').querySelectorAll('option')).map((o) => o.textContent);
    expect(options).toEqual([
      'All categories',
      'A · Structure and Masonry (3)',
      'B · Civil, Finishing and Waterproofing (5)',
      'C · Architectural Components (2)',
      'D · Electrical and HVAC (1)',
      'E · Plumbing and Sanitary (1)',
      'F · Site Setup (1)',
    ]);

    fireEvent.change(screen.getByLabelText('Search'), { target: { value: 'primer' } });
    expect(screen.getByText(`Showing 1 of ${TOTAL} items`)).toBeDefined();
    expect(table.tBodies).toHaveLength(1);
    expect(serialsOf(table.tBodies[0])).toEqual(['17a']);
    expect(screen.getByRole('button', { name: /B · Civil.*1 of 5 items/ })).toBeDefined();

    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'Site Setup' } });
    expect(screen.getByText('No rows match the filters')).toBeDefined();
    expect(screen.queryByRole('table')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
    expect(screen.getByText(`${TOTAL} items`)).toBeDefined();
    expect(screen.getByText('Bricks')).toBeDefined();

    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'excluded' } });
    const shown = Array.from(screen.getByRole('table', { name: /bill of quantities/i }).querySelectorAll('tbody'));
    expect(shown.flatMap((group) => serialsOf(group))).toEqual(['30', '58']);
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'allowance' } });
    expect(screen.getByText(`Showing 2 of ${TOTAL} items`)).toBeDefined();
    expect(screen.getByText('Switches and sockets')).toBeDefined();
    expect(screen.getByText('Site barricading')).toBeDefined();
  });

  it('sorts inside the groups when a header is clicked', () => {
    const table = renderTable();
    const header = (label: string) => screen.getByRole('button', { name: label }).closest('th');
    expect(header('S.No')?.getAttribute('aria-sort')).toBe('ascending');
    expect(header('Quantity')?.getAttribute('aria-sort')).toBe('none');
    expect(header('Quantity')?.getAttribute('scope')).toBe('col');

    fireEvent.click(screen.getByRole('button', { name: 'Quantity' }));
    expect(header('Quantity')?.getAttribute('aria-sort')).toBe('ascending');
    expect(header('S.No')?.getAttribute('aria-sort')).toBe('none');
    expect(serialsOf(table.tBodies[1])).toEqual(['17a', '17', '17b', '18', '22']); // inside Painting only

    fireEvent.click(screen.getByRole('button', { name: 'Quantity' }));
    expect(header('Quantity')?.getAttribute('aria-sort')).toBe('descending');
    expect(serialsOf(table.tBodies[1])).toEqual(['17b', '17', '17a', '18', '22']);
    expect(serialsOf(table.tBodies[0])).toEqual(['1', '2', '3']); // one row per sub-category: unchanged

    fireEvent.click(screen.getByRole('button', { name: 'S.No' }));
    expect(serialsOf(table.tBodies[1])).toEqual(['17', '17a', '17b', '18', '22']);
  });

  it('says so when the bill has no rows', () => {
    render(<BoqTable items={[]} />);
    expect(screen.getByText('No items in this bill')).toBeDefined();
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.queryByLabelText('Search')).toBeNull();
  });
});

// ---------------------------------------------------------------- API + page

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const jobEvent = (stage: string, status: string, progress: number, extra: Record<string, unknown> = {}) => ({
  job_id: 'job-1',
  status,
  stage,
  detail: `${stage} the plan`,
  progress,
  error: null,
  ...extra,
});

const DONE = [
  jobEvent('queued', 'queued', 0),
  jobEvent('parsing', 'running', 40),
  jobEvent('calculating', 'running', 80),
  jobEvent('done', 'done', 100),
];

function sse(events: unknown[]): Response {
  const text = events.map((event) => `event: progress\ndata: ${JSON.stringify(event)}\n\n`).join('');
  return new Response(`${text}event: end\ndata: {}\n\n`, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}

const PDF_FILE = () =>
  new Response('%PDF-1.7', {
    status: 200,
    headers: { 'Content-Type': 'application/pdf', 'Content-Disposition': 'attachment; filename="BOQ_Green_Villa.pdf"' },
  });

interface MockApi {
  start?: () => Response;
  events?: unknown[];
  result?: () => Response;
  exportFile?: () => Response;
}

function mockApi(api: MockApi = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith(BOQ_BASE) && init?.method === 'POST') return api.start?.() ?? json({ job_id: 'job-1' }, 202);
    if (url.endsWith('/jobs/job-1/events')) return sse(api.events ?? DONE);
    if (url.endsWith('/jobs/job-1/result')) return api.result?.() ?? json(RAW_BOQ_RESULT);
    if (url.includes(`${BOQ_BASE}/export/`)) return api.exportFile?.() ?? PDF_FILE();
    return json({ detail: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

type FetchMock = ReturnType<typeof mockApi>;

const callTo = (fetchMock: FetchMock, path: string) => {
  const call = fetchMock.mock.calls.find(([input]) => String(input).includes(path));
  if (!call) throw new Error(`no request to ${path}`);
  return { url: String(call[0]), init: call[1] ?? {} };
};

const pdf = (name = 'green-villa.pdf') => new File(['%PDF-1.7'], name, { type: 'application/pdf' });

function renderPage() {
  render(
    <MemoryRouter>
      <BoqPage />
    </MemoryRouter>,
  );
}

function pick(file: File) {
  fireEvent.change(screen.getByLabelText('Floor plan PDF'), { target: { files: [file] } });
}

async function generate(file = pdf()) {
  renderPage();
  pick(file);
  fireEvent.click(screen.getByRole('button', { name: 'Generate BOQ' }));
  return screen.findByRole('heading', { name: 'Green Villa' });
}

describe('BOQ page', () => {
  let downloads: string[];

  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(TOKEN_STORAGE_KEY, 'test-jwt-token');
    downloads = [];
    // jsdom has no object URLs and cannot follow a download link
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, writable: true, value: vi.fn(() => 'blob:boq') });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, writable: true, value: vi.fn() });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      downloads.push(this.download);
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('accepts PDFs only', () => {
    mockApi();
    renderPage();
    expect(screen.getByText(/drag and drop your floor plan pdf here/i)).toBeDefined();
    const startButton = screen.getByRole('button', { name: 'Generate BOQ' });
    expect(startButton.hasAttribute('disabled')).toBe(true);

    pick(new File(['x'], 'plan.png', { type: 'image/png' }));
    expect(screen.getByRole('alert').textContent).toMatch(/as a PDF file/i);
    expect(startButton.hasAttribute('disabled')).toBe(true);

    pick(pdf());
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByText('green-villa.pdf')).toBeDefined();
    expect(startButton.hasAttribute('disabled')).toBe(false);
  });

  it('uploads the PDF, shows the three steps, then the bill', async () => {
    const fetchMock = mockApi();
    renderPage();
    pick(pdf());
    fireEvent.click(screen.getByRole('button', { name: 'Generate BOQ' }));

    // the upload itself is the first step
    const steps = screen.getAllByRole('listitem').map((li) => li.textContent ?? '');
    expect(steps.map((text) => /^(Uploading|Parsing|Calculating)/.exec(text)?.[1])).toEqual(['Uploading', 'Parsing', 'Calculating']);
    expect(steps[0]).toMatch(/in progress/);
    expect(screen.getByRole('progressbar')).toBeDefined();

    expect(await screen.findByRole('heading', { name: 'Green Villa' })).toBeDefined();

    const upload = callTo(fetchMock, BOQ_BASE);
    expect(upload.url).toBe(`http://localhost:8000${BOQ_BASE}`);
    expect(upload.init.method).toBe('POST');
    const sent = upload.init.body instanceof FormData ? upload.init.body.get('file') : null;
    expect(sent instanceof File && sent.name).toBe('green-villa.pdf');
    expect(new Headers(upload.init.headers).get('Authorization')).toBe('Bearer test-jwt-token');
    expect(new Headers(callTo(fetchMock, '/jobs/job-1/result').init.headers).get('Authorization')).toBe('Bearer test-jwt-token');

    const summary = within(screen.getByRole('region', { name: 'Plan summary' }));
    expect(summary.getByText('1,234.50 m²')).toBeDefined();
    expect(summary.getByText('13,288.05 sq ft')).toBeDefined();
    const stat = (label: string) => summary.getByText(label).parentElement?.textContent;
    expect(stat('Levels')).toBe('Levels2');
    expect(stat('Rooms')).toBe('Rooms14');
    expect(stat('Bathrooms')).toBe('Bathrooms3');
    expect(stat('Items')).toBe(`Items${TOTAL}`);

    expect(screen.getByRole('table', { name: /bill of quantities/i })).toBeDefined();
    expect(screen.getByText('Bricks')).toBeDefined();
  });

  it('lists the warnings, folding the ones after the third', async () => {
    mockApi();
    await generate();
    const warnings = within(screen.getByRole('region', { name: 'Warnings' }));
    expect(warnings.getByRole('heading', { name: '4 warnings' })).toBeDefined();
    expect(warnings.getAllByRole('listitem')).toHaveLength(3);
    expect(warnings.queryByText(/plot boundary/)).toBeNull();

    const more = warnings.getByRole('button', { name: 'Show all 4 warnings' });
    expect(more.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(more);
    expect(warnings.getAllByRole('listitem')).toHaveLength(4);
    expect(warnings.getByText(/plot boundary/)).toBeDefined();
    expect(warnings.getByRole('button', { name: 'Show fewer warnings' }).getAttribute('aria-expanded')).toBe('true');
  });

  it('shows no warnings banner when there are none', async () => {
    mockApi({ result: () => json({ ...RAW_BOQ_RESULT, warnings: [] }) });
    await generate();
    expect(screen.queryByRole('region', { name: 'Warnings' })).toBeNull();
  });

  it('downloads the full list, not the filtered view, with only the contract keys', async () => {
    const fetchMock = mockApi();
    await generate();
    fireEvent.change(screen.getByLabelText('Search'), { target: { value: 'primer' } });
    expect(screen.getByText(`Showing 1 of ${TOTAL} items`)).toBeDefined();

    fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }));
    await waitFor(() => expect(downloads).toEqual(['BOQ_Green_Villa.pdf'])); // the server's file name

    const request = callTo(fetchMock, '/export/pdf');
    expect(request.url).toBe(`http://localhost:8000${BOQ_BASE}/export/pdf`);
    expect(request.init.method).toBe('POST');
    const headers = new Headers(request.init.headers);
    expect(headers.get('Authorization')).toBe('Bearer test-jwt-token');
    expect(headers.get('Content-Type')).toBe('application/json');
    const body: unknown = JSON.parse(String(request.init.body));
    expect(body).toEqual({
      items: RAW_BOQ_RESULT.items,
      warnings: RAW_BOQ_RESULT.warnings,
      geometry_summary: RAW_BOQ_RESULT.geometry_summary,
      project_metadata: RAW_BOQ_RESULT.project_metadata,
      assumptions: RAW_BOQ_RESULT.assumptions,
    });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Download PDF' }).hasAttribute('disabled')).toBe(false));
  });

  it('shows an export failure inline and lets the person try again', async () => {
    mockApi({ exportFile: () => json({ detail: 'The spreadsheet could not be built.' }, 500) });
    await generate();
    fireEvent.click(screen.getByRole('button', { name: 'Download Excel' }));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe('Excel download failed. The spreadsheet could not be built.');
    expect(downloads).toEqual([]);
    expect(screen.getByRole('button', { name: 'Download Excel' }).hasAttribute('disabled')).toBe(false);
    expect(screen.getByText('Bricks')).toBeDefined(); // the bill stays on screen
  });

  it("shows the job's error and offers another file", async () => {
    mockApi({
      events: [
        jobEvent('queued', 'queued', 0),
        jobEvent('parsing', 'running', 30),
        jobEvent('failed', 'failed', 30, { error: 'No floor plan was found in this PDF.', error_code: 'no_plan_found' }),
      ],
    });
    renderPage();
    pick(pdf());
    fireEvent.click(screen.getByRole('button', { name: 'Generate BOQ' }));
    expect((await screen.findByRole('alert')).textContent).toBe('No floor plan was found in this PDF.');
    expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Try another file' }));
    expect(screen.getByText(/drag and drop your floor plan pdf here/i)).toBeDefined();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('shows why an upload was refused', async () => {
    mockApi({ start: () => json({ detail: 'Only PDF files are accepted.' }, 400) });
    renderPage();
    pick(pdf());
    fireEvent.click(screen.getByRole('button', { name: 'Generate BOQ' }));
    expect((await screen.findByRole('alert')).textContent).toBe('Only PDF files are accepted.');
    expect(screen.getByRole('button', { name: 'Try another file' })).toBeDefined();
  });

  it('can fetch the result again without a second upload', async () => {
    let attempts = 0;
    const fetchMock = mockApi({
      result: () => (++attempts === 1 ? json({ detail: 'Result store is busy.' }, 503) : json(RAW_BOQ_RESULT)),
    });
    renderPage();
    pick(pdf());
    fireEvent.click(screen.getByRole('button', { name: 'Generate BOQ' }));
    expect((await screen.findByRole('alert')).textContent).toBe('Result store is busy.');

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByRole('heading', { name: 'Green Villa' })).toBeDefined();
    const uploads = fetchMock.mock.calls.filter(([input, init]) => String(input).endsWith(BOQ_BASE) && init?.method === 'POST');
    expect(uploads).toHaveLength(1);
  });

  it('resets the page for another plan', async () => {
    mockApi();
    await generate();
    fireEvent.click(screen.getByRole('button', { name: 'Upload another plan' }));
    expect(screen.getByText(/drag and drop your floor plan pdf here/i)).toBeDefined();
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.queryByText('green-villa.pdf')).toBeNull();
  });

  it('names a download after the source file when the server gives no name', async () => {
    mockApi({ exportFile: () => new Response('PK', { status: 200 }) });
    await boqApi.download('xlsx', RESULT);
    const { project_metadata: _dropped, ...rest } = RESULT;
    await boqApi.download('pdf', { ...rest, project_metadata: {} }, 'Site Plan.pdf');
    await boqApi.download('pdf', { ...rest, project_metadata: {} });
    expect(downloads).toEqual(['BOQ_green-villa.xlsx', 'BOQ_Site Plan.pdf', 'BOQ.pdf']);
  });

  it('sends nothing but the parts of the result to export', () => {
    const withLegacy = { ...RESULT, materials: [], materials_by_key: {}, level_summaries: [], room_breakdown: [] };
    const body = boqExportBody(withLegacy);
    expect(Object.keys(body).sort()).toEqual(['assumptions', 'geometry_summary', 'items', 'project_metadata', 'warnings']);
    expect(body.items).toBe(RESULT.items);
    expect(body.assumptions).toBe(RESULT.assumptions);

    // a result from an older server has no assumptions: the key is left out, not sent empty
    const { assumptions: _dropped, ...older } = withLegacy;
    expect(Object.keys(boqExportBody(older)).sort()).toEqual(['geometry_summary', 'items', 'project_metadata', 'warnings']);
  });
});

describe('a saved bill', () => {
  beforeEach(() => localStorage.setItem(TOKEN_STORAGE_KEY, 'test-token'));
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it('opens from /boq?bill=<id> as it was made, without uploading anything', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith(`${BOQ_BASE}/history/b1`))
        return json({ id: 'b1', name: 'Villa A.pdf', source: 'upload', created_at: '2026-11-20T08:00:00Z', summary: { items: TOTAL }, result: RAW_BOQ_RESULT });
      return json({ detail: 'Not found' }, 404);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(
      <MemoryRouter initialEntries={['/boq?bill=b1']}>
        <BoqPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByRole('row').length).toBeGreaterThan(TOTAL / 2));
    expect(fetchMock.mock.calls.some(([u]) => String(u).endsWith(BOQ_BASE))).toBe(false);
  });
});
