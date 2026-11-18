/**
 * Pure logic of the BOQ page: number formatting, serial order, search and filters, sorting,
 * grouping, progress steps and file names. No React in here, so every rule is easy to test.
 *
 * Everything is driven by the rows themselves: no row count, category list or item code is
 * assumed anywhere.
 */
import { BOQ_STEPS, type BoqExportFormat, type BoqItem } from './boqSchemas';

// ------------------------------------------------------------------ numbers

/** Same grouping as the server's PDF and Excel exports: 1,234,567.50 */
const NUMBER_LOCALE = 'en-US';
const MAX_DECIMALS = 6;

/** Units that are measured (2 decimals). Any other unit is counted (whole numbers). */
const MEASURE_UNITS = new Set([
  'm',
  'rm',
  'm2',
  'm²',
  'sqm',
  'sqft',
  'm3',
  'm³',
  'cum',
  'cft',
  'kg',
  't',
  'tonne',
  'tonnes',
  'metric_tons',
  'l',
  'litre',
  'litres',
]);

export function isMeasureUnit(unit: string): boolean {
  return MEASURE_UNITS.has(unit.trim().toLowerCase());
}

/** Decimals for a quantity: the row's own `quantity_decimals` when given, else by its unit. */
export function quantityDecimals(unit: string, decimals?: number | null): number {
  if (typeof decimals === 'number' && Number.isInteger(decimals) && decimals >= 0) {
    return Math.min(decimals, MAX_DECIMALS);
  }
  return isMeasureUnit(unit) ? 2 : 0;
}

/** 12480 -> "12,480"; 1234.5 with 2 decimals -> "1,234.50". */
export function formatNumber(value: number, decimals: number): string {
  // a value that rounds to zero is shown as "0", never "-0"
  const shown = Math.abs(value) < 0.5 / 10 ** decimals ? 0 : value;
  return shown.toLocaleString(NUMBER_LOCALE, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

/** Whole numbers for counts, 2 decimals for measures, with thousands separators. */
export function formatQuantity(quantity: number, unit: string, decimals?: number | null): string {
  return formatNumber(quantity, quantityDecimals(unit, decimals));
}

const UNIT_LABELS = new Map<string, string>([
  ['m2', 'm²'],
  ['m3', 'm³'],
]);

/** A unit as shown on screen: "m2" -> "m²", "metric_tons" -> "metric tons". */
export function displayUnit(unit: string): string {
  const trimmed = unit.trim();
  return UNIT_LABELS.get(trimmed.toLowerCase()) ?? trimmed.replace(/_/g, ' ');
}

// ---------------------------------------------------------- serial numbers

const TEXT_ORDER: Intl.CollatorOptions = { numeric: true, sensitivity: 'base' };

function compareText(a: string, b: string): number {
  return a.localeCompare(b, undefined, TEXT_ORDER);
}

function serialParts(serial: number | string): { number: number; suffix: string } {
  if (typeof serial === 'number') return { number: serial, suffix: '' };
  const match = /^\s*(\d+(?:\.\d+)?)\s*(.*?)\s*$/.exec(serial);
  // a serial that does not start with a number goes last, in text order
  if (!match) return { number: Number.POSITIVE_INFINITY, suffix: serial.trim() };
  return { number: Number(match[1]), suffix: match[2] };
}

/** Natural order of serial numbers: 2 < 10 and 17 < 17a < 17b < 18. */
export function compareSerial(a: number | string, b: number | string): number {
  const x = serialParts(a);
  const y = serialParts(b);
  if (x.number !== y.number) return x.number < y.number ? -1 : 1;
  return compareText(x.suffix, y.suffix);
}

// ------------------------------------------------------------------ status

export type BoqStatus = 'included' | 'excluded' | 'allowance';
export type BoqStatusFilter = 'all' | BoqStatus;

export const STATUS_LABELS: Record<BoqStatus, string> = {
  included: 'Included',
  excluded: 'Excluded',
  allowance: 'Allowance',
};

/**
 * What the Status column shows for a row: "Excluded" when it is left out of the quote,
 * "Allowance" when its quantity is an allowance (a row can be both), otherwise "Included".
 */
export function itemStatuses(item: BoqItem): BoqStatus[] {
  const statuses: BoqStatus[] = [];
  if (item.quote_status === 'EXCLUDED_FROM_QUOTE') statuses.push('excluded');
  if (item.calc_type === 'allowance') statuses.push('allowance');
  return statuses.length > 0 ? statuses : ['included'];
}

// ----------------------------------------------------------------- filters

export interface BoqFilters {
  search: string;
  /** Category name; '' means every category. */
  category: string;
  status: BoqStatusFilter;
}

export const NO_FILTERS: BoqFilters = { search: '', category: '', status: 'all' };

export function hasActiveFilters(filters: BoqFilters): boolean {
  return filters.search.trim() !== '' || filters.category !== '' || filters.status !== 'all';
}

/** Every word typed must be found in the name, item code, category, sub-category or note. */
export function matchesSearch(item: BoqItem, search: string): boolean {
  const words = search.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;
  const text = [item.name, item.item_code, item.category, item.sub_category, item.note].join('\n').toLowerCase();
  return words.every((word) => text.includes(word));
}

/** The status filter matches what the Status column shows. */
export function matchesStatus(item: BoqItem, status: BoqStatusFilter): boolean {
  return status === 'all' || itemStatuses(item).includes(status);
}

export function categoryKey(item: BoqItem): string {
  return item.category.trim();
}

export function filterItems(items: readonly BoqItem[], filters: BoqFilters): BoqItem[] {
  return items.filter(
    (item) =>
      (filters.category === '' || categoryKey(item) === filters.category) &&
      matchesStatus(item, filters.status) &&
      matchesSearch(item, filters.search),
  );
}

// ----------------------------------------------------------------- sorting

export type BoqSortKey = 'serial_no' | 'category' | 'sub_category' | 'name' | 'unit' | 'quantity' | 'status';
export type SortDirection = 'asc' | 'desc';

export interface BoqSort {
  key: BoqSortKey;
  direction: SortDirection;
}

export const DEFAULT_SORT: BoqSort = { key: 'serial_no', direction: 'asc' };

/** Clicking the sorted column flips its direction; another column starts ascending. */
export function nextSort(current: BoqSort, key: BoqSortKey): BoqSort {
  if (current.key !== key) return { key, direction: 'asc' };
  return { key, direction: current.direction === 'asc' ? 'desc' : 'asc' };
}

/** Included rows first, then allowances, then rows left out of the quote. */
function statusRank(item: BoqItem): number {
  return (item.quote_status === 'EXCLUDED_FROM_QUOTE' ? 2 : 0) + (item.calc_type === 'allowance' ? 1 : 0);
}

function compareBy(key: BoqSortKey, a: BoqItem, b: BoqItem): number {
  switch (key) {
    case 'serial_no':
      return compareSerial(a.serial_no, b.serial_no);
    case 'name':
      return compareText(a.name, b.name);
    case 'unit':
      return compareText(a.unit, b.unit);
    case 'quantity':
      return a.quantity - b.quantity;
    case 'status':
      return statusRank(a) - statusRank(b);
    default:
      // category and sub-category order the sections, not the rows inside them
      return 0;
  }
}

/** Rows in the chosen order; equal rows stay in serial order. */
export function sortItems(items: readonly BoqItem[], sort: BoqSort = DEFAULT_SORT): BoqItem[] {
  const sign = sort.direction === 'asc' ? 1 : -1;
  return [...items].sort(
    (a, b) => sign * compareBy(sort.key, a, b) || compareSerial(a.serial_no, b.serial_no),
  );
}

// ---------------------------------------------------------------- grouping

export interface BoqSubGroup {
  key: string;
  label: string;
  items: BoqItem[];
}

export interface BoqGroup {
  /** The category name (trimmed); also the value of the category filter. */
  key: string;
  code: string | null;
  /** "A · Structure and Masonry" when the rows carry a category code. */
  label: string;
  /** Rows in this group. */
  count: number;
  subGroups: BoqSubGroup[];
}

const UNCATEGORISED = 'Uncategorised';
const NO_SUB_CATEGORY = 'General';

export function categoryLabel(category: string, code?: string | null): string {
  const name = category.trim() || UNCATEGORISED;
  const prefix = code?.trim();
  return prefix ? `${prefix} · ${name}` : name;
}

/**
 * Rows grouped by category, then sub-category.
 *
 * Categories are ordered by their code (A, B, C...) when they have one, otherwise in the
 * order they first appear by serial number; sub-categories likewise by first appearance.
 * The sort applies inside each sub-category. Sorting by the Category or Sub-category
 * column orders those sections instead (their rows stay in serial order).
 */
export function groupItems(items: readonly BoqItem[], sort: BoqSort = DEFAULT_SORT): BoqGroup[] {
  const sign = sort.direction === 'asc' ? 1 : -1;
  const found = new Map<string, { code: string | null; subs: Map<string, BoqItem[]> }>();

  for (const item of sortItems(items)) {
    const key = categoryKey(item);
    let group = found.get(key);
    if (!group) {
      group = { code: null, subs: new Map() };
      found.set(key, group);
    }
    group.code ??= item.category_code?.trim() || null;
    const subKey = item.sub_category.trim();
    const rows = group.subs.get(subKey);
    if (rows) rows.push(item);
    else group.subs.set(subKey, [item]);
  }

  const groups: BoqGroup[] = [...found].map(([key, group]) => {
    const subGroups: BoqSubGroup[] = [...group.subs].map(([subKey, rows]) => ({
      key: subKey,
      label: subKey || NO_SUB_CATEGORY,
      items: sortItems(rows, sort),
    }));
    if (sort.key === 'sub_category') subGroups.sort((a, b) => sign * compareText(a.label, b.label));
    return {
      key,
      code: group.code,
      label: categoryLabel(key, group.code),
      count: subGroups.reduce((total, sub) => total + sub.items.length, 0),
      subGroups,
    };
  });

  // Array.sort is stable, so groups that compare equal keep their first-appearance order
  if (sort.key === 'category') {
    groups.sort((a, b) => sign * (compareText(a.code ?? '', b.code ?? '') || compareText(a.key, b.key)));
  } else {
    groups.sort((a, b) => {
      if (a.code && b.code) return compareText(a.code, b.code);
      if (a.code || b.code) return a.code ? -1 : 1;
      return 0;
    });
  }
  return groups;
}

// ---------------------------------------------------------------- progress

export type BoqStepState = 'todo' | 'active' | 'done';

/** Job stage -> index of the step it belongs to (BOQ_STEPS.length once everything is done). */
const STAGE_STEP = new Map<string, number>([
  ['queued', 0],
  ['uploading', 0],
  ['parsing', 1],
  ['calculating', 2],
  ['done', BOQ_STEPS.length],
]);

/**
 * State of the three visible steps (Uploading, Parsing, Calculating).
 * "Uploading" is active while the file is being sent and until the job starts parsing.
 */
export function stepStates(progress: { uploading: boolean; stages: readonly string[] }): BoqStepState[] {
  const reached = progress.uploading ? 0 : Math.max(0, ...progress.stages.map((stage) => STAGE_STEP.get(stage) ?? 0));
  return BOQ_STEPS.map((_, index) => (index < reached ? 'done' : index === reached ? 'active' : 'todo'));
}

// ------------------------------------------------------------------- files

export const MAX_PDF_BYTES = 50 * 1024 * 1024;

/** Why a picked file cannot be used, or null when it is fine. */
export function validatePdf(file: { name: string; size: number; type?: string }): string | null {
  const isPdf = file.name.toLowerCase().endsWith('.pdf') || file.type === 'application/pdf';
  if (!isPdf) return 'Please upload an architectural document in PDF format.';
  if (file.size > MAX_PDF_BYTES) return 'File size exceeds 50MB limit.';
  if (file.size === 0) return 'This PDF is empty. Please choose another file.';
  return null;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Last path segment, without control characters; null when nothing is left. */
function cleanFileName(name: string): string | null {
  const parts = name.split(/[\\/]/);
  const cleaned = (parts[parts.length - 1] ?? '').replace(/\p{Cc}/gu, '').trim();
  return cleaned || null;
}

/** The file name a download response asks for (Content-Disposition), if it gives one. */
export function fileNameFromDisposition(header: string | null | undefined): string | null {
  if (!header) return null;
  // RFC 5987 form first: filename*=UTF-8''BOQ_Green%20Villa.pdf
  const encoded = /filename\*\s*=\s*[^']*'[^']*'([^;]+)/i.exec(header);
  if (encoded) {
    try {
      const name = cleanFileName(decodeURIComponent(encoded[1].trim()));
      if (name) return name;
    } catch {
      // badly encoded: use the plain name below
    }
  }
  const plain = /filename\s*=\s*(?:"((?:[^"\\]|\\.)*)"|([^;]+))/i.exec(header);
  if (!plain) return null;
  return cleanFileName(plain[1] !== undefined ? plain[1].replace(/\\(.)/g, '$1') : plain[2]);
}

/** Name used when the server gives none: BOQ_<source file base name>.pdf / .xlsx */
export function exportFileName(format: BoqExportFormat, sourceName?: string | null): string {
  const base = (cleanFileName(sourceName ?? '') ?? '')
    .replace(/\.pdf$/i, '')
    .replace(/[:*?"<>|]+/g, '_')
    .trim();
  return base ? `BOQ_${base}.${format}` : `BOQ.${format}`;
}
