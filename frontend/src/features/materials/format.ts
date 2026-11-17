export const ESTIMATE_NOTE = 'Quantities are planning estimates. Verify by site measurement before ordering.';

/** 92.4 -> "92.4", 12 -> "12" (one decimal at most). */
export const fmt = (n: number) => (Math.round(n * 10) / 10).toString();
