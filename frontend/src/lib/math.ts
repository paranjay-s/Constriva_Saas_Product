export const clamp = (v: number, min: number, max: number): number =>
  Math.min(Math.max(v, min), max);

export const smooth = (a: number, b: number, x: number): number => {
  const t = clamp((x - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
};

