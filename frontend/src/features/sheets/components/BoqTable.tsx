/**
 * The bill as an interactive table: search, category and status filters, sortable columns,
 * collapsible category groups with sub-category subheaders, and rows that expand to show
 * their components and note. Search, filters and sorting only change what is on screen.
 */
import { Fragment, useId, useMemo, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { ChevronRightIcon } from '../../../components/ui/Icons';
import { Input } from '../../../components/ui/Input';
import {
  type BoqFilters,
  type BoqSort,
  type BoqSortKey,
  type BoqStatus,
  type BoqStatusFilter,
  DEFAULT_SORT,
  NO_FILTERS,
  STATUS_LABELS,
  categoryLabel,
  displayUnit,
  filterItems,
  formatQuantity,
  groupItems,
  hasActiveFilters,
  itemStatuses,
  nextSort,
} from '../boqLogic';
import type { BoqItem } from '../boqSchemas';

interface Column {
  key: BoqSortKey;
  label: string;
  /** Extra classes for the header and body cells of this column. */
  cell?: string;
  numeric?: boolean;
}

/*
 * Narrow screens keep S.No, Material and Quantity, so the bill fits a 360 px phone without
 * sideways scrolling. The other columns are folded in, not lost: Category and Sub-category
 * are the group header and subheader, the unit sits under the quantity and the status
 * under the material name.
 */
const COLUMNS: readonly Column[] = [
  { key: 'serial_no', label: 'S.No', cell: 'w-14' },
  { key: 'category', label: 'Category', cell: 'hidden lg:table-cell' },
  { key: 'sub_category', label: 'Sub-category', cell: 'hidden md:table-cell' },
  { key: 'name', label: 'Material' },
  { key: 'unit', label: 'Unit', cell: 'hidden sm:table-cell' },
  { key: 'quantity', label: 'Quantity', numeric: true },
  { key: 'status', label: 'Status', cell: 'hidden sm:table-cell' },
];

const STATUS_OPTIONS: readonly { value: BoqStatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'included', label: STATUS_LABELS.included },
  { value: 'excluded', label: STATUS_LABELS.excluded },
  { value: 'allowance', label: STATUS_LABELS.allowance },
];

const STATUS_STYLES: Record<BoqStatus, string> = {
  included: 'border-[#10B981]/40 bg-[#102A1A] text-[#A7F3D0]',
  excluded: 'border-[#FFB4AB]/40 bg-[#351010] text-[#FFB4AB]',
  allowance: 'border-[#C5A77B]/40 bg-[#C5A77B]/10 text-[#E2C294]',
};

const FOCUS = 'focus:outline-none focus-visible:ring-2 focus-visible:ring-[#C5A77B]';
const FIELD_LABEL = 'text-xs font-semibold uppercase tracking-wider text-[#A6A6A6]';
const SELECT = `h-11 w-full rounded border border-[#303030] bg-[#181818] px-3 text-sm text-white transition-colors duration-150 focus:border-[#C5A77B] focus:outline-none`;
const CELL = 'border-b border-[#262626] px-3 py-2.5 align-top';

const itemsLabel = (n: number) => (n === 1 ? '1 item' : `${n} items`);

function StatusBadges({ item }: { item: BoqItem }) {
  return (
    <span className="flex flex-wrap gap-1">
      {itemStatuses(item).map((status) => (
        <span
          key={status}
          className={`inline-block whitespace-nowrap rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${STATUS_STYLES[status]}`}
        >
          {STATUS_LABELS[status]}
        </span>
      ))}
    </span>
  );
}

function RowDetail({ item }: { item: BoqItem }) {
  const note = item.note.trim();
  return (
    <div className="flex flex-col gap-3 md:pl-9">
      {item.components.length > 0 && (
        <table className="w-full max-w-xl text-xs">
          <caption className="sr-only">Components of {item.name}</caption>
          <thead>
            <tr className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">
              <th scope="col" className="pb-1 pr-3 text-left font-semibold">
                Component
              </th>
              <th scope="col" className="pb-1 pr-3 text-right font-semibold">
                Quantity
              </th>
              <th scope="col" className="pb-1 text-left font-semibold">
                Unit
              </th>
            </tr>
          </thead>
          <tbody>
            {item.components.map((part, index) => (
              <tr key={index}>
                <th scope="row" className="py-1 pr-3 text-left font-normal text-[#D5D5D5]">
                  {part.label}
                </th>
                <td className="whitespace-nowrap py-1 pr-3 text-right font-mono tabular-nums text-white">
                  {formatQuantity(part.quantity, part.unit, part.quantity_decimals)}
                </td>
                <td className="whitespace-nowrap py-1 text-left text-[#A6A6A6]">{displayUnit(part.unit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {note && (
        <div className="max-w-2xl text-xs leading-relaxed text-[#A6A6A6]">
          <span className="font-semibold text-[#D5D5D5]">Note: </span>
          {note}
        </div>
      )}
    </div>
  );
}

interface ItemRowProps {
  item: BoqItem;
  rowId: string;
  open: boolean;
  onToggle: () => void;
}

function ItemRow({ item, rowId, open, onToggle }: ItemRowProps) {
  const expandable = item.components.length > 0 || item.note.trim() !== '';
  const detailId = `${rowId}-detail`;
  const name = (
    <span className="flex min-w-0 flex-col gap-0.5">
      <span className="break-words text-sm text-white">{item.name}</span>
      <span className="break-all font-mono text-[11px] text-[#737373]">{item.item_code}</span>
    </span>
  );

  return (
    <>
      <tr className="hover:bg-white/[0.03]">
        <td className={`${CELL} whitespace-nowrap font-mono text-xs text-[#A6A6A6]`}>{item.serial_no}</td>
        <td className={`${CELL} hidden text-xs text-[#A6A6A6] lg:table-cell`}>
          {categoryLabel(item.category, item.category_code)}
        </td>
        <td className={`${CELL} hidden text-xs text-[#A6A6A6] md:table-cell`}>{item.sub_category}</td>
        <th scope="row" className={`${CELL} min-w-[9rem] text-left font-normal`}>
          <div className="flex flex-col gap-1.5">
            {expandable ? (
              <button
                type="button"
                aria-expanded={open}
                aria-controls={open ? detailId : undefined}
                onClick={onToggle}
                className={`flex w-full cursor-pointer items-start gap-2 rounded text-left ${FOCUS}`}
              >
                <ChevronRightIcon
                  size={16}
                  aria-hidden="true"
                  className={`mt-0.5 h-4 w-4 shrink-0 text-[#C5A77B] transition-transform ${open ? 'rotate-90' : ''}`}
                />
                {name}
              </button>
            ) : (
              <span className="flex items-start gap-2">
                <span aria-hidden="true" className="h-4 w-4 shrink-0" />
                {name}
              </span>
            )}
            {/* narrow screens: the Status column is folded in here */}
            <div className="pl-6 sm:hidden">
              <StatusBadges item={item} />
            </div>
          </div>
        </th>
        <td className={`${CELL} hidden whitespace-nowrap text-xs text-[#A6A6A6] sm:table-cell`}>{displayUnit(item.unit)}</td>
        <td className={`${CELL} whitespace-nowrap text-right font-mono text-sm tabular-nums text-white`}>
          {formatQuantity(item.quantity, item.unit, item.quantity_decimals)}
          {/* narrow screens: the Unit column is folded in here */}
          <span className="block font-sans text-[11px] text-[#A6A6A6] sm:hidden">{displayUnit(item.unit)}</span>
        </td>
        <td className={`${CELL} hidden sm:table-cell`}>
          <StatusBadges item={item} />
        </td>
      </tr>
      {expandable && open && (
        <tr id={detailId}>
          <td colSpan={COLUMNS.length} className="border-b border-[#262626] bg-[#141414] px-3 py-3">
            <RowDetail item={item} />
          </td>
        </tr>
      )}
    </>
  );
}

function toggled(set: ReadonlySet<string>, key: string): Set<string> {
  const next = new Set(set);
  if (!next.delete(key)) next.add(key);
  return next;
}

export function BoqTable({ items }: { items: readonly BoqItem[] }) {
  const baseId = useId();
  const [filters, setFilters] = useState<BoqFilters>(NO_FILTERS);
  const [sort, setSort] = useState<BoqSort>(DEFAULT_SORT);
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(() => new Set());
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => new Set());

  // rows have no guaranteed unique field, so each gets an id from its place in the full list
  const rowIds = useMemo(() => new Map(items.map((item, index) => [item, `${baseId}row${index}`])), [items, baseId]);
  /** Every category of the full list (filter options and "x of y" counts). */
  const categories = useMemo(() => groupItems(items), [items]);
  const visible = useMemo(() => filterItems(items, filters), [items, filters]);
  const groups = useMemo(() => groupItems(visible, sort), [visible, sort]);

  if (items.length === 0) {
    return (
      <div role="status" className="flex flex-col items-center gap-1.5 rounded border border-[#303030] bg-[#141414] px-4 py-12 text-center">
        <div className="font-display text-lg font-semibold text-white">No items in this bill</div>
        <div className="max-w-md text-xs text-[#A6A6A6]">
          The plan was read, but no quantities came out of it. Try uploading another plan.
        </div>
      </div>
    );
  }

  const totals = new Map(categories.map((group) => [group.key, group.count]));
  const filtering = hasActiveFilters(filters);
  const allCollapsed = groups.length > 0 && groups.every((group) => collapsed.has(group.key));
  const searchId = `${baseId}search`;
  const categoryId = `${baseId}category`;
  const statusId = `${baseId}status`;

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_16rem_11rem]">
        <div className="sm:col-span-2 lg:col-span-1">
          <Input
            id={searchId}
            type="search"
            label="Search"
            placeholder="Material, item code, category or note"
            autoComplete="off"
            value={filters.search}
            onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor={categoryId} className={FIELD_LABEL}>
            Category
          </label>
          <select
            id={categoryId}
            value={filters.category}
            onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))}
            className={SELECT}
          >
            <option value="">All categories</option>
            {categories.map((group) => (
              <option key={group.key} value={group.key}>
                {group.label} ({group.count})
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor={statusId} className={FIELD_LABEL}>
            Status
          </label>
          <select
            id={statusId}
            value={filters.status}
            onChange={(e) => {
              const status = STATUS_OPTIONS.find((option) => option.value === e.target.value)?.value ?? 'all';
              setFilters((f) => ({ ...f, status }));
            }}
            className={SELECT}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div role="status" aria-live="polite" className="font-mono text-xs text-[#A6A6A6]">
          {filtering ? `Showing ${visible.length} of ${itemsLabel(items.length)}` : itemsLabel(items.length)}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {filtering && visible.length > 0 && (
            <Button variant="ghost" size="sm" onClick={() => setFilters(NO_FILTERS)}>
              Clear filters
            </Button>
          )}
          {groups.length > 0 && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setCollapsed(allCollapsed ? new Set() : new Set(categories.map((group) => group.key)))}
            >
              {allCollapsed ? 'Expand all' : 'Collapse all'}
            </Button>
          )}
        </div>
      </div>

      {visible.length === 0 ? (
        <div role="status" className="flex flex-col items-center gap-3 rounded border border-[#303030] bg-[#141414] px-4 py-12 text-center">
          <div className="flex flex-col gap-1">
            <div className="font-display text-lg font-semibold text-white">No rows match the filters</div>
            <div className="text-xs text-[#A6A6A6]">Try another search word, category or status.</div>
          </div>
          <Button variant="secondary" size="sm" onClick={() => setFilters(NO_FILTERS)}>
            Clear filters
          </Button>
        </div>
      ) : (
        <div className="max-h-[72vh] overflow-auto rounded border border-[#303030] bg-[#181818]">
          <table className="w-full border-separate border-spacing-0 text-left">
            <caption className="sr-only">Bill of quantities, grouped by category and sub-category</caption>
            <thead>
              <tr>
                {COLUMNS.map((column) => {
                  const active = sort.key === column.key;
                  const direction = active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none';
                  return (
                    <th
                      key={column.key}
                      scope="col"
                      aria-sort={direction}
                      className={`sticky top-0 z-10 border-b border-[#303030] bg-[#202020] px-3 py-2.5 ${
                        column.numeric ? 'text-right' : 'text-left'
                      } ${column.cell ?? ''}`}
                    >
                      <button
                        type="button"
                        onClick={() => setSort((current) => nextSort(current, column.key))}
                        title={`Sort by ${column.label}`}
                        className={`inline-flex cursor-pointer items-center gap-1 whitespace-nowrap rounded font-mono text-[11px] font-semibold uppercase tracking-wider hover:text-white ${FOCUS} ${
                          active ? 'text-[#C5A77B]' : 'text-[#A6A6A6]'
                        }`}
                      >
                        {column.label}
                        <span aria-hidden="true" className="text-[9px]">
                          {active ? (sort.direction === 'asc' ? '▲' : '▼') : '↕'}
                        </span>
                      </button>
                    </th>
                  );
                })}
              </tr>
            </thead>
            {groups.map((group) => {
              const isCollapsed = collapsed.has(group.key);
              const total = totals.get(group.key) ?? group.count;
              return (
                <tbody key={group.key}>
                  <tr>
                    <th scope="rowgroup" colSpan={COLUMNS.length} className="border-b border-[#303030] bg-[#1C1C1C] p-0 text-left">
                      <button
                        type="button"
                        aria-expanded={!isCollapsed}
                        onClick={() => setCollapsed((current) => toggled(current, group.key))}
                        className={`flex w-full cursor-pointer flex-wrap items-center gap-x-2 gap-y-1 px-3 py-2.5 text-left hover:bg-white/[0.04] ${FOCUS} focus-visible:ring-inset`}
                      >
                        <ChevronRightIcon
                          size={16}
                          aria-hidden="true"
                          className={`h-4 w-4 shrink-0 text-[#C5A77B] transition-transform ${isCollapsed ? '' : 'rotate-90'}`}
                        />
                        <span className="min-w-0 flex-1 font-display text-sm font-semibold text-white sm:flex-none">{group.label}</span>
                        <span className="whitespace-nowrap rounded-full border border-[#303030] bg-[#141414] px-2 py-0.5 font-mono text-[11px] font-normal text-[#A6A6A6]">
                          {group.count === total ? itemsLabel(total) : `${group.count} of ${itemsLabel(total)}`}
                        </span>
                      </button>
                    </th>
                  </tr>
                  {!isCollapsed &&
                    group.subGroups.map((sub) => (
                      <Fragment key={sub.key}>
                        <tr>
                          <th
                            scope="colgroup"
                            colSpan={COLUMNS.length}
                            className="border-b border-[#262626] bg-[#141414] px-3 py-1.5 text-left font-mono text-[11px] font-semibold uppercase tracking-wider text-[#C5A77B]"
                          >
                            {sub.label}
                          </th>
                        </tr>
                        {sub.items.map((item) => {
                          const rowId = rowIds.get(item) ?? `${baseId}${group.key}${sub.key}${String(item.serial_no)}`;
                          return (
                            <ItemRow
                              key={rowId}
                              item={item}
                              rowId={rowId}
                              open={expanded.has(rowId)}
                              onToggle={() => setExpanded((current) => toggled(current, rowId))}
                            />
                          );
                        })}
                      </Fragment>
                    ))}
                </tbody>
              );
            })}
          </table>
        </div>
      )}
    </div>
  );
}
