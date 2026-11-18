import { describe, expect, it } from 'vitest';
import { RAW_BOQ_RESULT } from './boqFixture';
import {
  DEFAULT_SORT,
  NO_FILTERS,
  compareSerial,
  displayUnit,
  exportFileName,
  fileNameFromDisposition,
  filterItems,
  formatNumber,
  formatQuantity,
  groupItems,
  hasActiveFilters,
  isMeasureUnit,
  itemStatuses,
  matchesSearch,
  nextSort,
  quantityDecimals,
  sortItems,
  stepStates,
} from './boqLogic';
import { type BoqItem, boqResultSchema } from './boqSchemas';

const ITEMS = boqResultSchema.parse(RAW_BOQ_RESULT).items;
const serials = (items: readonly BoqItem[]) => items.map((item) => item.serial_no);
const codes = (items: readonly BoqItem[]) => items.map((item) => item.item_code);
const byCode = (code: string): BoqItem => {
  const item = ITEMS.find((candidate) => candidate.item_code === code);
  if (!item) throw new Error(`no ${code} row in the fixture`);
  return item;
};

describe('BOQ number formatting', () => {
  it('shows counts as whole numbers with thousands separators', () => {
    expect(formatQuantity(12480, 'nos')).toBe('12,480');
    expect(formatQuantity(12480.4, 'nos')).toBe('12,480');
    expect(formatQuantity(412, 'bags (50 kg)')).toBe('412');
    expect(formatQuantity(1234567, 'pcs')).toBe('1,234,567');
    expect(formatQuantity(0, 'nos')).toBe('0');
  });

  it('shows measures with 2 decimals and thousands separators', () => {
    expect(formatQuantity(1234.5, 'm2')).toBe('1,234.50');
    expect(formatQuantity(1234567.891, 'kg')).toBe('1,234,567.89');
    expect(formatQuantity(0.5, 'm³')).toBe('0.50');
    expect(formatQuantity(96, 'rm')).toBe('96.00');
  });

  it('knows which units are measures; every other unit is a count', () => {
    const measures = ['m', 'm2', 'm²', 'm3', 'm³', 'kg', 't', 'tonne', 'metric_tons', 'l', 'litre', 'rm', 'sqm', 'cum', 'sqft'];
    for (const unit of measures) expect(isMeasureUnit(unit), unit).toBe(true);
    expect(isMeasureUnit(' KG ')).toBe(true);
    for (const unit of ['nos', 'pcs', 'bags (50 kg)', 'set', 'points', '']) expect(isMeasureUnit(unit), unit).toBe(false);
  });

  it("uses the row's quantity_decimals when present, else the unit", () => {
    expect(quantityDecimals('bags', 2)).toBe(2);
    expect(quantityDecimals('kg', 0)).toBe(0);
    expect(quantityDecimals('kg', null)).toBe(2);
    expect(quantityDecimals('nos')).toBe(0);
    expect(formatQuantity(412.6, 'bags', 2)).toBe('412.60');
    expect(formatQuantity(86.44, 'l', 0)).toBe('86');
    // the fixture's paint row has no quantity_decimals: litres are a measure
    const paint = byCode('interior_paint');
    expect(paint.quantity_decimals).toBeUndefined();
    expect(formatQuantity(paint.quantity, paint.unit, paint.quantity_decimals)).toBe('86.40');
  });

  it('never shows a negative zero', () => {
    expect(formatQuantity(-0.001, 'kg')).toBe('0.00');
    expect(formatNumber(-0.2, 0)).toBe('0');
  });

  it('writes units for the screen', () => {
    expect(displayUnit('m2')).toBe('m²');
    expect(displayUnit('m3')).toBe('m³');
    expect(displayUnit('metric_tons')).toBe('metric tons');
    expect(displayUnit('bags (50 kg)')).toBe('bags (50 kg)');
  });
});

describe('BOQ serial order', () => {
  it('compares serial numbers naturally, lettered rows included', () => {
    expect(compareSerial(17, '17a')).toBeLessThan(0);
    expect(compareSerial('17a', '17b')).toBeLessThan(0);
    expect(compareSerial('17b', 18)).toBeLessThan(0);
    expect(compareSerial(2, 10)).toBeLessThan(0);
    expect(compareSerial('2', '10')).toBeLessThan(0);
    expect(compareSerial('17a', '17A')).toBe(0);
    expect(compareSerial(18, '17b')).toBeGreaterThan(0);
    expect(compareSerial(59, 'extra')).toBeLessThan(0); // no number: goes last
  });

  it('sorts rows by serial number by default', () => {
    expect(serials(sortItems(ITEMS))).toEqual([1, 2, 3, 17, '17a', '17b', 18, 22, 27, 30, 33, 48, 58]);
    expect(serials(sortItems(ITEMS, { key: 'serial_no', direction: 'desc' }))).toEqual([
      58, 48, 33, 30, 27, 22, 18, '17b', '17a', 17, 3, 2, 1,
    ]);
    expect(serials(ITEMS)[0]).toBe(18); // the input is left as it was
  });
});

describe('BOQ sorting', () => {
  it('toggles the direction on the same column and starts ascending on another', () => {
    expect(nextSort(DEFAULT_SORT, 'serial_no')).toEqual({ key: 'serial_no', direction: 'desc' });
    expect(nextSort({ key: 'serial_no', direction: 'desc' }, 'serial_no')).toEqual(DEFAULT_SORT);
    expect(nextSort({ key: 'serial_no', direction: 'desc' }, 'quantity')).toEqual({ key: 'quantity', direction: 'asc' });
  });

  it('sorts by quantity, name and status; equal rows stay in serial order', () => {
    expect(codes(sortItems(ITEMS, { key: 'quantity', direction: 'desc' })).slice(0, 3)).toEqual(['bricks', 'steel', 'false_ceiling']);
    expect(codes(sortItems(ITEMS, { key: 'name', direction: 'asc' })).slice(0, 2)).toEqual(['bricks', 'cement']);
    // status: included, then allowance, then excluded
    const byStatus = sortItems(ITEMS, { key: 'status', direction: 'asc' });
    expect(serials(byStatus)).toEqual([1, 2, 3, 17, '17a', '17b', 18, 22, 27, 48, 33, 30, 58]);
    // unit "nos" is shared by four rows: they keep serial order
    const nos = sortItems(ITEMS, { key: 'unit', direction: 'asc' }).filter((item) => item.unit === 'nos');
    expect(serials(nos)).toEqual([1, 27, 33, 48]);
  });
});

describe('BOQ grouping', () => {
  it('groups by category in code order, with labels and row counts', () => {
    const groups = groupItems(ITEMS);
    expect(groups.map((g) => g.label)).toEqual([
      'A · Structure and Masonry',
      'B · Civil, Finishing and Waterproofing',
      'C · Architectural Components',
      'D · Electrical and HVAC',
      'E · Plumbing and Sanitary',
      'F · Site Setup',
    ]);
    expect(groups.map((g) => g.count)).toEqual([3, 5, 2, 1, 1, 1]);
    expect(groups.map((g) => g.code)).toEqual(['A', 'B', 'C', 'D', 'E', 'F']);
  });

  it('puts sub-category subheaders inside each group, rows in serial order', () => {
    const [, civil, components] = groupItems(ITEMS);
    expect(civil.subGroups.map((s) => s.label)).toEqual(['Painting', 'Ceilings', 'External works']);
    expect(serials(civil.subGroups[0].items)).toEqual([17, '17a', '17b']);
    // "External works" exists in two categories and stays separate
    expect(serials(civil.subGroups[2].items)).toEqual([22]);
    expect(components.subGroups.map((s) => s.label)).toEqual(['Doors and glazing', 'External works']);
    expect(serials(components.subGroups[1].items)).toEqual([30]);
  });

  it('sorts inside the groups: the groups themselves stay where they are', () => {
    const groups = groupItems(ITEMS, { key: 'quantity', direction: 'desc' });
    expect(groups.map((g) => g.code)).toEqual(['A', 'B', 'C', 'D', 'E', 'F']);
    expect(groups[1].subGroups.map((s) => s.label)).toEqual(['Painting', 'Ceilings', 'External works']);
    expect(serials(groups[1].subGroups[0].items)).toEqual(['17b', 17, '17a']); // 310, 86.4, 43.2
  });

  it('orders the sections when sorting by category or sub-category', () => {
    expect(groupItems(ITEMS, { key: 'category', direction: 'desc' }).map((g) => g.code)).toEqual(['F', 'E', 'D', 'C', 'B', 'A']);
    const civil = groupItems(ITEMS, { key: 'sub_category', direction: 'asc' })[1];
    expect(civil.subGroups.map((s) => s.label)).toEqual(['Ceilings', 'External works', 'Painting']);
    expect(serials(civil.subGroups[2].items)).toEqual([17, '17a', '17b']);
  });

  it('needs no category codes: groups then follow the serial numbers', () => {
    const plain = ITEMS.map((item) => ({ ...item, category_code: undefined }));
    const groups = groupItems(plain);
    expect(groups.map((g) => g.label)).toEqual([
      'Structure and Masonry',
      'Civil, Finishing and Waterproofing',
      'Architectural Components',
      'Electrical and HVAC',
      'Plumbing and Sanitary',
      'Site Setup',
    ]);
    expect(groups.every((g) => g.code === null)).toBe(true);
  });

  it('copes with any number of rows and with missing names', () => {
    expect(groupItems([])).toEqual([]);
    const odd = [{ ...byCode('bricks'), category: ' ', category_code: null, sub_category: '' }];
    const [group] = groupItems(odd);
    expect(group.label).toBe('Uncategorised');
    expect(group.subGroups[0].label).toBe('General');
  });
});

describe('BOQ search and filters', () => {
  it('searches the name, item code, category, sub-category and note', () => {
    const search = (text: string) => codes(sortItems(filterItems(ITEMS, { ...NO_FILTERS, search: text })));
    expect(search('primer')).toEqual(['interior_primer']); // name
    expect(search('WASH_BASINS')).toEqual(['wash_basins']); // item code, any case
    expect(search('plumbing')).toEqual(['wash_basins']); // category
    expect(search('painting')).toEqual(['interior_paint', 'interior_primer', 'wall_putty']); // sub-category
    expect(search('breakage')).toEqual(['bricks']); // note
    expect(search('interior')).toEqual(['interior_paint', 'interior_primer']);
    expect(search('  interior   EMULSION ')).toEqual(['interior_paint']); // every word must match
    expect(search('no such thing')).toEqual([]);
    expect(search('   ')).toHaveLength(ITEMS.length);
    expect(matchesSearch(byCode('bricks'), 'masonry bricks')).toBe(true);
  });

  it('filters by category', () => {
    const rows = filterItems(ITEMS, { ...NO_FILTERS, category: 'Architectural Components' });
    expect(serials(sortItems(rows))).toEqual([27, 30]);
  });

  it('filters by status, matching what the Status column shows', () => {
    const status = (value: 'included' | 'excluded' | 'allowance') =>
      serials(sortItems(filterItems(ITEMS, { ...NO_FILTERS, status: value })));
    expect(status('excluded')).toEqual([30, 58]);
    expect(status('allowance')).toEqual([33, 58]); // 58 is both
    expect(status('included')).toEqual([1, 2, 3, 17, '17a', '17b', 18, 22, 27, 48]);
    expect(filterItems(ITEMS, NO_FILTERS)).toHaveLength(ITEMS.length);
  });

  it('combines search, category and status', () => {
    const rows = filterItems(ITEMS, { search: 'external', category: 'Architectural Components', status: 'excluded' });
    expect(codes(rows)).toEqual(['driveway_paving']);
    expect(filterItems(ITEMS, { search: 'external', category: 'Site Setup', status: 'all' })).toEqual([]);
  });

  it('knows when a filter is active', () => {
    expect(hasActiveFilters(NO_FILTERS)).toBe(false);
    expect(hasActiveFilters({ ...NO_FILTERS, search: '  ' })).toBe(false);
    expect(hasActiveFilters({ ...NO_FILTERS, search: 'steel' })).toBe(true);
    expect(hasActiveFilters({ ...NO_FILTERS, category: 'Site Setup' })).toBe(true);
    expect(hasActiveFilters({ ...NO_FILTERS, status: 'excluded' })).toBe(true);
  });

  it('gives each row its statuses', () => {
    expect(itemStatuses(byCode('bricks'))).toEqual(['included']);
    expect(itemStatuses(byCode('driveway_paving'))).toEqual(['excluded']);
    expect(itemStatuses(byCode('switches_sockets'))).toEqual(['allowance']);
    expect(itemStatuses(byCode('site_barricading'))).toEqual(['excluded', 'allowance']);
  });
});

describe('BOQ progress steps', () => {
  it('walks through Uploading, Parsing and Calculating', () => {
    expect(stepStates({ uploading: true, stages: [] })).toEqual(['active', 'todo', 'todo']);
    expect(stepStates({ uploading: false, stages: ['queued'] })).toEqual(['active', 'todo', 'todo']);
    expect(stepStates({ uploading: false, stages: ['queued', 'uploading', 'parsing'] })).toEqual(['done', 'active', 'todo']);
    expect(stepStates({ uploading: false, stages: ['queued', 'parsing', 'calculating'] })).toEqual(['done', 'done', 'active']);
    expect(stepStates({ uploading: false, stages: ['parsing', 'calculating', 'done'] })).toEqual(['done', 'done', 'done']);
    // a failed or unknown stage does not move the steps
    expect(stepStates({ uploading: false, stages: ['parsing', 'failed'] })).toEqual(['done', 'active', 'todo']);
  });
});

describe('BOQ files', () => {
  it('reads the file name a download asks for', () => {
    expect(fileNameFromDisposition('attachment; filename="BOQ_green-villa.pdf"')).toBe('BOQ_green-villa.pdf');
    expect(fileNameFromDisposition('attachment; filename=BOQ.xlsx')).toBe('BOQ.xlsx');
    expect(fileNameFromDisposition("attachment; filename=\"BOQ.pdf\"; filename*=UTF-8''BOQ_Green%20Villa.pdf")).toBe('BOQ_Green Villa.pdf');
    expect(fileNameFromDisposition('attachment; filename="../../etc/BOQ.pdf"')).toBe('BOQ.pdf');
    expect(fileNameFromDisposition('attachment')).toBeNull();
    expect(fileNameFromDisposition(null)).toBeNull();
  });

  it('names an export after the source file when the server gives no name', () => {
    expect(exportFileName('pdf', 'green-villa.pdf')).toBe('BOQ_green-villa.pdf');
    expect(exportFileName('xlsx', 'Green Villa.PDF')).toBe('BOQ_Green Villa.xlsx');
    expect(exportFileName('xlsx', 'plans/site: A?.pdf')).toBe('BOQ_site_ A_.xlsx');
    expect(exportFileName('pdf', null)).toBe('BOQ.pdf');
  });
});
