/**
 * The whole bill: 59 items in 64 rows, exactly as the backend returns them.
 *
 * `boqFullBill.fixture.json` is written by the backend (the test fixture of
 * docs/materials_formula_spec.md, section 8) and a backend test fails when it goes stale,
 * so these tests run against the real row contract: lettered rows, every category and
 * sub-category, breakdowns, excluded and allowance rows.
 */
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { boqExportBody } from './boqApi';
import RAW_FULL_BILL from './boqFullBill.fixture.json';
import { filterItems, groupItems, sortItems } from './boqLogic';
import { boqResultSchema } from './boqSchemas';
import { BoqTable } from './components/BoqTable';

const RESULT = boqResultSchema.parse(RAW_FULL_BILL);
const LETTERED = ['17a', '17b', '18a', '18b', '47a', '47b', '53a', '53b', '57a', '57b'];

const subGroupsOf = (label: string) => {
  const group = groupItems(RESULT.items).find((candidate) => candidate.label === label);
  if (!group) throw new Error(`no ${label} group`);
  return group.subGroups.map((sub) => ({ label: sub.label, serials: sub.items.map((item) => item.serial_no) }));
};

describe('full bill: contract', () => {
  it('parses all 64 rows and changes none of them', () => {
    expect(RESULT.items).toHaveLength(64);
    expect(RESULT.items).toEqual(RAW_FULL_BILL.items);
    const serials = RESULT.items.map((item) => String(item.serial_no));
    expect(new Set(serials).size).toBe(64);
    expect(serials.filter((serial) => !/^\d+$/.test(serial))).toEqual(LETTERED);
    // every item number from 1 to 59 is there, five of them as two lettered rows
    expect([...new Set(serials.map((serial) => Number.parseInt(serial, 10)))]).toEqual(
      Array.from({ length: 59 }, (_, index) => index + 1),
    );
  });

  it('arrives in serial order, lettered rows after their number', () => {
    expect(sortItems(RESULT.items).map((item) => item.serial_no)).toEqual(RESULT.items.map((item) => item.serial_no));
  });

  it('sends every row to export, lettered rows included', () => {
    const body = boqExportBody(RESULT);
    expect(body.items).toHaveLength(64);
    expect(body.items).toEqual(RAW_FULL_BILL.items);
    expect(Object.keys(body).sort()).toEqual(['geometry_summary', 'items', 'project_metadata', 'warnings']);
  });
});

describe('full bill: grouping', () => {
  it('has the six categories with their row counts', () => {
    const groups = groupItems(RESULT.items);
    expect(groups.map((group) => [group.label, group.count])).toEqual([
      ['A · Structure and Masonry', 7],
      ['B · Civil, Finishing and Waterproofing', 18],
      ['C · Architectural Components', 8],
      ['D · Electrical and HVAC', 12],
      ['E · Plumbing and Sanitary', 17],
      ['F · Site Setup', 2],
    ]);
    expect(groups.reduce((total, group) => total + group.subGroups.length, 0)).toBe(27);
  });

  it('keeps a sub-category together when its serial numbers are not consecutive', () => {
    expect(subGroupsOf('B · Civil, Finishing and Waterproofing')).toEqual([
      { label: 'Roofing and waterproofing', serials: [8, 9, 10, 11] },
      { label: 'Tiling', serials: [12, 13, 14] },
      { label: 'Stone and feature', serials: [15, 16] },
      { label: 'Painting', serials: ['17a', '17b', 19, 21] },
      { label: 'Ceilings', serials: ['18a', '18b'] },
      { label: 'External render', serials: [20] },
      { label: 'External works', serials: [22, 23] },
    ]);
    expect(subGroupsOf('D · Electrical and HVAC')).toEqual([
      { label: 'Cabling and containment', serials: [32, 42] },
      { label: 'Wiring devices', serials: [33] },
      { label: 'Distribution and protection', serials: [34, 35] },
      { label: 'Lighting', serials: [36, 39, 40, 41] },
      { label: 'Ventilation and controls', serials: [37, 43] },
      { label: 'Water heating', serials: [38] },
    ]);
    expect(subGroupsOf('E · Plumbing and Sanitary')).toEqual([
      { label: 'Drainage', serials: [44, '53a', '53b', 54, '57a', '57b'] },
      { label: 'Valves and fittings', serials: [45, 46, '47a', '47b'] },
      { label: 'Sanitary fixtures', serials: [48, 49, 50, 55, 56] },
      { label: 'Pumps and storage', serials: [51, 52] },
    ]);
  });

  it('filters by what the Status column shows', () => {
    const serialsWith = (status: 'excluded' | 'allowance') =>
      filterItems(RESULT.items, { search: '', category: '', status }).map((item) => item.serial_no);
    expect(serialsWith('excluded')).toEqual([22, 23, 30, 31, 52, 56]);
    expect(serialsWith('allowance')).toEqual([14, 16, 25, 31, 39, 41, 42]);
  });
});

describe('full bill: table', () => {
  function renderTable() {
    render(<BoqTable items={RESULT.items} />);
    const table = screen.getByRole('table', { name: /bill of quantities/i });
    if (!(table instanceof HTMLTableElement)) throw new Error('the bill is not a <table>');
    return table;
  }

  /** The item rows of the bill: those that start with a serial number cell. */
  const itemRows = (table: HTMLTableElement) =>
    Array.from(table.rows).filter((row) => row.cells[0]?.tagName === 'TD' && row.cells.length > 1);

  const rowOf = (name: string): HTMLTableRowElement => {
    const row = screen.getByText(name).closest('tr');
    if (!row) throw new Error(`no row for ${name}`);
    return row;
  };

  it('shows every row once, under six category groups and their sub-category subheaders', () => {
    const table = renderTable();
    expect(screen.getByText('64 items')).toBeDefined();
    expect(table.tBodies).toHaveLength(6);
    const rows = itemRows(table);
    expect(rows).toHaveLength(64);
    expect(table.querySelectorAll('th[scope="colgroup"]')).toHaveLength(27);

    const serials = rows.map((row) => row.cells[0].textContent ?? '');
    expect(new Set(serials).size).toBe(64);
    for (const serial of LETTERED) expect(serials, serial).toContain(serial);
    // on screen the rows follow the groups: Painting (17a, 17b, 19, 21) before Ceilings (18a, 18b)
    expect(serials.slice(serials.indexOf('17a'), serials.indexOf('20') + 1)).toEqual([
      '17a',
      '17b',
      '19',
      '21',
      '18a',
      '18b',
      '20',
    ]);
    for (const item of RESULT.items) expect(screen.getAllByText(item.name).length, item.name).toBeGreaterThan(0);
  });

  it('shows each quantity with its unit: whole numbers for counts, 2 decimals for measures', () => {
    renderTable();
    // cells: S.No, Category, Sub-category, Material, Unit, Quantity, Status
    const shown = (name: string) => {
      const cells = rowOf(name).cells;
      return [cells[4].textContent, cells[5].firstChild?.textContent];
    };
    expect(shown('AAC blocks')).toEqual(['pieces', '6,143']);
    expect(shown('Steel rebar')).toEqual(['kg', '9,856.00']);
    expect(shown('Cement')).toEqual(['50 kg bags', '331']);
    expect(shown('Sand')).toEqual(['m³', '28.54']);
    expect(shown('Floor tiles and skirting')).toEqual(['m²', '186.40']);
    expect(shown('Interior wall paint')).toEqual(['L', '194']);
    expect(shown('Interior wall primer')).toEqual(['L', '87']);
    expect(shown('Cable (single core)')).toEqual(['LM', '2,552']);
    expect(shown('LED strip')).toEqual(['LM', '66.15']);
    expect(shown('Shower mixer sets')).toEqual(['Sets', '2']);
    expect(shown('Interlock paving')).toEqual(['m²', '0.00']);
    expect(shown('Project signboard')).toEqual(['No.', '1']);
  });

  it('marks the excluded and allowance rows', () => {
    renderTable();
    const badges = (name: string) => {
      const cells = Array.from(rowOf(name).cells);
      return Array.from(cells[cells.length - 1].querySelectorAll('span > span')).map((badge) => badge.textContent);
    };
    expect(badges('Water tanks')).toEqual(['Excluded']);
    expect(badges('Gates')).toEqual(['Excluded', 'Allowance']);
    expect(badges('Chandeliers')).toEqual(['Allowance']);
    expect(badges('Water closets')).toEqual(['Included']);
  });

  it('opens a row to show the breakdown of one product', () => {
    renderTable();
    const partsOf = (name: string) => {
      const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      fireEvent.click(screen.getByRole('button', { name: new RegExp(`^${escaped}`) }));
      const parts = screen.getByRole('table', { name: `Components of ${name}` });
      return within(parts)
        .getAllByRole('row')
        .slice(1)
        .map((row) => Array.from((row as HTMLTableRowElement).cells).map((cell) => cell.textContent));
    };
    expect(partsOf('Switches and sockets')).toEqual([
      ['13 A twin sockets', '42', 'Nos'],
      ['Light switches', '14', 'Nos'],
      ['Heater and cooker switches', '5', 'Nos'],
    ]);
    expect(partsOf('Water tanks')).toEqual([
      ['Ground tank', '2,000', 'L'],
      ['Roof tank', '1,500', 'L'],
    ]);
    expect(partsOf('Steel rebar')).toEqual([
      ['12 m rods (12 mm average)', '925', 'Nos'],
      ['Weight', '9.86', 't'],
    ]);
    expect(partsOf('Cable (single core)')).toEqual([['Coils of 91.4 m', '28', 'Nos']]);
    expect(screen.getByText(/35% lighting, 40% sockets, 20% AC and heaters, 5% cooker/)).toBeDefined();
  });

  it('filters the full bill by status and by category', () => {
    const table = renderTable();
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'excluded' } });
    expect(screen.getByText('Showing 6 of 64 items')).toBeDefined();
    expect(itemRows(table).map((row) => row.cells[0].textContent)).toEqual(['22', '23', '30', '31', '52', '56']);

    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'all' } });
    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'Plumbing and Sanitary' } });
    expect(screen.getByText('Showing 17 of 64 items')).toBeDefined();
    expect(itemRows(table).map((row) => row.cells[0].textContent)).toEqual([
      '44',
      '53a',
      '53b',
      '54',
      '57a',
      '57b',
      '45',
      '46',
      '47a',
      '47b',
      '48',
      '49',
      '50',
      '55',
      '56',
      '51',
      '52',
    ]);
  });
});
