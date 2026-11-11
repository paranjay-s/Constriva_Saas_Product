// utils/units.ts

export const FT_TO_M = 0.3048;
export const INCH_TO_M = 0.0254;

export function ftInToMeters(ft: number, inches: number = 0): number {
  return Math.round((ft * FT_TO_M + inches * INCH_TO_M) * 10000) / 10000;
}

/**
 * Parses a single dimension token like "10'2\"", "12'", "6\"", "3.5m", "3500mm"
 */
export function parseSingleFtIn(token: string): number | null {
  const t = token.trim();
  if (!t) return null;

  // Metric meters: "3.5m", "3.5 M"
  const mMatch = t.match(/^([0-9.]+)\s*m$/i);
  if (mMatch) {
    const val = parseFloat(mMatch[1]);
    return !isNaN(val) ? val : null;
  }

  // Metric millimeters: "3500mm"
  const mmMatch = t.match(/^([0-9.]+)\s*mm$/i);
  if (mmMatch) {
    const val = parseFloat(mmMatch[1]);
    return !isNaN(val) ? val / 1000 : null;
  }

  // Inches only: e.g. '6"'
  if (/^[0-9.]+"$/.test(t)) {
    const inch = parseFloat(t.replace(/"/g, ''));
    return !isNaN(inch) ? inch * INCH_TO_M : null;
  }

  // Feet and inches: e.g. "10'2\"", "10'", "10'6"
  if (t.includes("'")) {
    const parts = t.replace(/"/g, '').split("'");
    const ft = parseFloat(parts[0]) || 0;
    const inch = parts[1] ? parseFloat(parts[1]) || 0 : 0;
    return ftInToMeters(ft, inch);
  }

  const val = parseFloat(t);
  if (!isNaN(val)) {
    return ftInToMeters(val, 0);
  }

  return null;
}

/**
 * Parses dimension strings like "10'2\"X12'", "14' X 12'8\"", "3.5m x 4.2m", "23' X 4'4\""
 */
export function parseFtIn(str: string): { w: number; d: number } | null {
  if (!str) return null;

  const upper = str.toUpperCase().replace(/\s+/g, ' ');
  // Look for separator: 'X', '×', 'BY', '*'
  const match = upper.match(/([0-9.'"M]+)\s*(?:X|×|\*|BY)\s*([0-9.'"M]+)/i);
  if (!match) {
    const wdMatch = upper.match(/([0-9.'"M]+)\s*(?:WD|WIDE|WIDTH)/i);
    if (wdMatch) {
      const w = parseSingleFtIn(wdMatch[1]);
      if (w !== null) return { w, d: w };
    }
    return null;
  }

  const w = parseSingleFtIn(match[1]);
  const d = parseSingleFtIn(match[2]);

  if (w !== null && d !== null && w > 0 && d > 0) {
    return { w, d };
  }

  return null;
}

function formatSingleMetersToFtIn(meters: number): string {
  const totalInches = Math.round(meters / INCH_TO_M);
  const ft = Math.floor(totalInches / 12);
  const inch = totalInches % 12;
  return inch > 0 ? `${ft}'${inch}"` : `${ft}'`;
}

/**
 * Formats meters to imperial string representation e.g. 10'2" or 10'2" × 12'
 */
export function formatMetersToFtIn(wMeters: number, dMeters?: number): string {
  if (dMeters !== undefined && dMeters > 0) {
    return `${formatSingleMetersToFtIn(wMeters)} × ${formatSingleMetersToFtIn(dMeters)}`;
  }
  return formatSingleMetersToFtIn(wMeters);
}
