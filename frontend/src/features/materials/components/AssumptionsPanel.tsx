/**
 * Everything the numbers depend on, editable: the size, ceiling height, wastage and
 * coverage per material. "Update" recalculates on the server without a new photo analysis.
 */
import { useState } from 'react';
import type { ManualSpace, Material, MaterialReport, Overrides } from '../schemas';
import { fmt } from '../format';

interface Props {
  report: MaterialReport;
  materials: Material[];
  busy: boolean;
  onApply: (space: ManualSpace | null, overrides: Overrides) => void;
}

const parse = (s: string): number | undefined => {
  const n = Number(s);
  return s.trim() !== '' && Number.isFinite(n) && n >= 0 ? n : undefined;
};

export function AssumptionsPanel({ report, materials, busy, onApply }: Props) {
  const t = report.target;
  const wall = t?.wall ?? null;
  const room = t?.room ?? null;
  const manual = t?.source === 'manual';
  const [a, setA] = useState(() => fmt(wall?.width_ft ?? room?.length_ft ?? 0));
  const [b, setB] = useState(() => fmt(room?.width_ft ?? 0));
  const [h, setH] = useState(() => fmt(wall?.height_ft ?? room?.height_ft ?? 0));
  const [wastage, setWastage] = useState<Record<string, string>>({});
  const [coverage, setCoverage] = useState<Record<string, string>>({});

  const byId = new Map(materials.map((m) => [m.id, m]));
  const lineMaterials = Array.from(new Map(report.lines.map((l) => [l.material_id, l])).values());

  const apply = () => {
    let space: ManualSpace | null = null;
    const overrides: Overrides = { wastage_pct: {}, coverage_ratio: {} };
    if (manual && wall && parse(a) && parse(h)) space = { kind: 'wall', unit: 'ft', length: parse(a)!, height: parse(h)!, label: wall.label };
    if (manual && room && parse(a) && parse(b)) space = { kind: 'room', unit: 'ft', length: parse(a)!, width: parse(b)!, height: parse(h), label: room.name };
    if (!manual && room && parse(h)) overrides.ceiling_height_ft = parse(h);
    for (const [id, v] of Object.entries(wastage)) if (parse(v) !== undefined) overrides.wastage_pct![id] = parse(v)!;
    for (const [id, v] of Object.entries(coverage)) if (parse(v) !== undefined) overrides.coverage_ratio![id] = Math.min(parse(v)!, 100) / 100;
    onApply(space, overrides);
  };

  const box = 'w-16 rounded border border-[#3A404B] bg-transparent px-1.5 py-1 text-right text-sm text-white';
  return (
    <section aria-label="Assumptions" className="space-y-3 rounded-xl border border-white/10 p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-[#9AA3B2]">Assumptions (edit and update)</h2>
      {t && (
        <div className="flex flex-wrap items-end gap-3 text-xs text-[#9AA3B2]">
          {manual && (
            <label className="flex flex-col gap-1">
              {wall ? 'Wall width (ft)' : 'Length (ft)'}
              <input aria-label={wall ? 'Wall width (ft)' : 'Length (ft)'} className={box} value={a} onChange={(e) => setA(e.target.value)} />
            </label>
          )}
          {manual && room && (
            <label className="flex flex-col gap-1">
              Width (ft)
              <input aria-label="Width (ft)" className={box} value={b} onChange={(e) => setB(e.target.value)} />
            </label>
          )}
          {(wall || room) && (
            <label className="flex flex-col gap-1">
              {wall ? 'Wall height (ft)' : 'Ceiling height (ft)'}
              <input aria-label={wall ? 'Wall height (ft)' : 'Ceiling height (ft)'} className={box} value={h} onChange={(e) => setH(e.target.value)} />
            </label>
          )}
        </div>
      )}
      {lineMaterials.length > 0 && (
        <table className="w-full text-xs text-[#D5DAE1]">
          <thead>
            <tr className="text-left text-[10px] uppercase text-[#5C6370]">
              <th className="font-normal">Material</th>
              <th className="text-right font-normal">Wastage %</th>
              <th className="text-right font-normal">Coverage %</th>
            </tr>
          </thead>
          <tbody>
            {lineMaterials.map((l) => (
              <tr key={l.material_id}>
                <td className="py-1">{byId.get(l.material_id)?.display_name ?? l.material}</td>
                <td className="py-1 text-right">
                  <input
                    aria-label={`Wastage for ${l.material}`}
                    className={box}
                    value={wastage[l.material_id] ?? fmt(l.wastage_pct)}
                    onChange={(e) => setWastage({ ...wastage, [l.material_id]: e.target.value })}
                  />
                </td>
                <td className="py-1 text-right">
                  <input
                    aria-label={`Coverage for ${l.material}`}
                    className={box}
                    value={coverage[l.material_id] ?? fmt(l.coverage_ratio * 100)}
                    onChange={(e) => setCoverage({ ...coverage, [l.material_id]: e.target.value })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {report.assumptions.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-4 text-xs text-[#9AA3B2]">
          {report.assumptions.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
      )}
      <button
        type="button"
        disabled={busy}
        onClick={apply}
        className="rounded-md bg-[#C5A77B] px-3 py-1.5 text-xs font-medium text-black disabled:opacity-50"
      >
        {busy ? 'Updating…' : 'Update quantities'}
      </button>
    </section>
  );
}
