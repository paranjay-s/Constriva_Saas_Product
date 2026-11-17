/** Two compact tables: the materials found, and the quantities (with the working on demand). */
import { useState } from 'react';
import { ESTIMATE_NOTE, fmt } from '../format';
import type { Material, MaterialReport, QuantityLine } from '../schemas';

const BADGE: Record<string, string> = {
  high: 'bg-[#2E7D4F]/20 text-[#7BD99A]',
  medium: 'bg-[#B58A2E]/20 text-[#F1C76B]',
  low: 'bg-[#E5484D]/20 text-[#F2A0A2]',
};

const TH = 'px-3 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-[#5C6370]';
const TD = 'px-3 py-2.5 align-top';

function MaterialRow({ m, n }: { m: Material; n: number }) {
  const details = [m.finish, m.pattern, m.colour, m.size_hint].filter(Boolean).join(', ');
  return (
    <tr className="border-t border-white/5">
      <td className={`${TD} w-6 text-[#5C6370]`}>{n}</td>
      <td className={TD}>
        <p className="font-medium text-white">{m.display_name}</p>
        {m.replaces && <p className="mt-0.5 text-[11px] text-[#C5A77B]">Your choice, instead of {m.replaces}</p>}
        {m.confidence !== 'high' && m.look_alikes.length > 0 && (
          <p className="mt-0.5 text-[11px] text-[#9AA3B2]">Could also be: {m.look_alikes.join(', ')}</p>
        )}
      </td>
      <td className={`${TD} capitalize text-[#D5DAE1]`}>
        {m.surface}
        {m.coverage_ratio != null && m.coverage_ratio < 1 && (
          <span className="text-[#5C6370]"> · ~{Math.round(m.coverage_ratio * 100)}%</span>
        )}
      </td>
      <td className={`${TD} hidden text-[#9AA3B2] md:table-cell`}>{details || '—'}</td>
      <td className={TD}>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium capitalize ${BADGE[m.confidence] ?? ''}`}>
          {m.confidence}
        </span>
      </td>
    </tr>
  );
}

function LineRows({ line }: { line: QuantityLine }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <tr className="border-t border-white/5">
        <td className={TD}>
          <p className="text-white">{line.material}</p>
          <p className="text-[11px] text-[#5C6370]">{line.application}</p>
        </td>
        <td className={`${TD} text-right tabular-nums`}>
          <p className="font-semibold text-white">{fmt(line.total_qty)} {line.unit}</p>
          <p className="text-[11px] text-[#5C6370]">
            {fmt(line.net_qty)} + {fmt(line.wastage_pct)}%
          </p>
        </td>
        <td className={`${TD} text-right text-[#D5DAE1]`}>
          {line.buy_qty != null ? `${line.buy_qty} ${line.buy_unit ?? ''}` : '—'}
        </td>
        <td className={`${TD} text-right`}>
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
            className="text-xs text-[#C5A77B] hover:underline"
          >
            {open ? 'Hide' : 'How'}
          </button>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={4} className="bg-white/[0.02] px-3 pb-3 pt-1">
            <ol className="space-y-0.5 text-xs text-[#9AA3B2]">
              {line.breakdown.map((b, i) => (
                <li key={i} className="flex justify-between gap-4">
                  <span>{b.label}</span>
                  <span className="tabular-nums">
                    {b.formula} = <span className="text-white">{fmt(b.value)}</span>
                  </span>
                </li>
              ))}
            </ol>
          </td>
        </tr>
      )}
    </>
  );
}

function Table({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="overflow-hidden rounded-xl border border-white/10">
      <header className="flex items-baseline justify-between gap-2 border-b border-white/10 bg-white/[0.02] px-3 py-2">
        <h2 className="text-sm font-medium text-white">{title}</h2>
        {sub && <span className="truncate text-xs text-[#5C6370]">{sub}</span>}
      </header>
      <div className="overflow-x-auto">{children}</div>
    </section>
  );
}

export function ResultView({
  materials,
  report,
  focusNote,
}: {
  materials: Material[];
  report: MaterialReport | null | undefined;
  focusNote?: string;
}) {
  return (
    <div className="space-y-4">
      {focusNote && (
        <p className="rounded-lg bg-[#B58A2E]/10 px-3 py-2 text-xs text-[#F1C76B]">{focusNote}</p>
      )}

      <Table title="Materials found" sub={`${materials.length} item${materials.length === 1 ? '' : 's'}`}>
        {materials.length === 0 ? (
          <p className="px-3 py-4 text-sm text-[#9AA3B2]">No finish materials identified.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className={TH}>#</th>
                <th className={TH}>Material</th>
                <th className={TH}>Where</th>
                <th className={`${TH} hidden md:table-cell`}>Finish / details</th>
                <th className={TH}>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {materials.map((m, i) => (
                <MaterialRow key={m.id} m={m} n={i + 1} />
              ))}
            </tbody>
          </table>
        )}
      </Table>

      {report && report.lines.length > 0 && (
        <Table title="Quantities" sub={report.target?.label}>
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className={TH}>Material</th>
                <th className={`${TH} text-right`}>Total</th>
                <th className={`${TH} text-right`}>To buy</th>
                <th className={TH} />
              </tr>
            </thead>
            <tbody>
              {report.lines.map((l, i) => (
                <LineRows key={`${l.material_id}-${i}`} line={l} />
              ))}
            </tbody>
          </table>
        </Table>
      )}

      {report && report.supporting.length > 0 && (
        <Table title="Also needed" sub="supporting items, worked out from the areas">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className={TH}>Item</th>
                <th className={TH}>For</th>
                <th className={`${TH} text-right`}>Quantity</th>
              </tr>
            </thead>
            <tbody>
              {report.supporting.map((s, i) => (
                <tr key={i} className="border-t border-white/5" title={s.basis}>
                  <td className={`${TD} text-white`}>{s.item}</td>
                  <td className={`${TD} text-[#9AA3B2]`}>{s.material}</td>
                  <td className={`${TD} text-right tabular-nums text-[#D5DAE1]`}>
                    {s.qty} {s.unit}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Table>
      )}

      <p role="note" className="text-[11px] text-[#5C6370]">
        {report?.note || ESTIMATE_NOTE}
      </p>
    </div>
  );
}
