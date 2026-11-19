/** Small text helpers for the dashboard pages. */

const DAY = 86_400_000;

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

/** "today", "yesterday" or a short date such as "14 nov 2026" (the year is dropped for this year). */
export function dayLabel(iso: string | undefined, now: Date = new Date()): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const diff = Math.round((startOfDay(now) - startOfDay(d)) / DAY);
  if (diff === 0) return 'today';
  if (diff === 1) return 'yesterday';
  return shortDate(d, d.getFullYear() !== now.getFullYear());
}

export function shortDate(d: Date, withYear = true): string {
  return d
    .toLocaleDateString('en-GB', { day: 'numeric', month: 'short', ...(withYear ? { year: 'numeric' } : {}) })
    .toLowerCase();
}

export const plural = (n: number, one: string, many = `${one}s`): string => `${n} ${n === 1 ? one : many}`;
