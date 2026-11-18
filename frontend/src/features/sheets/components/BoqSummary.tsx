/** Summary strip above the bill: built area, levels, rooms, bathrooms and item count. */
import { formatNumber } from '../boqLogic';
import type { BoqGeometrySummary } from '../boqSchemas';

interface Stat {
  label: string;
  value: string;
  secondary?: string;
}

export function BoqSummary({ summary, itemCount }: { summary: BoqGeometrySummary; itemCount: number }) {
  const sqft = summary.a_built_total_sqft;
  const stats: Stat[] = [
    {
      label: 'Built area',
      value: `${formatNumber(summary.a_built_total_m2, 2)} m²`,
      secondary: typeof sqft === 'number' ? `${formatNumber(sqft, 2)} sq ft` : undefined,
    },
    { label: 'Levels', value: formatNumber(summary.levels_count, 0) },
    { label: 'Rooms', value: formatNumber(summary.rooms_count, 0) },
    { label: 'Bathrooms', value: formatNumber(summary.bathrooms_count, 0) },
    { label: 'Items', value: formatNumber(itemCount, 0) },
  ];

  return (
    <section aria-label="Plan summary">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {stats.map((stat, index) => (
          <div
            key={stat.label}
            className={`flex flex-col gap-0.5 rounded border border-[#303030] bg-[#141414] p-3 ${
              index === 0 ? 'col-span-2 sm:col-span-1' : ''
            }`}
          >
            <dt className="font-mono text-[10px] uppercase tracking-wider text-[#A6A6A6]">{stat.label}</dt>
            <dd className="m-0 font-mono text-lg font-bold text-[#C5A77B]">{stat.value}</dd>
            {stat.secondary && <dd className="m-0 font-mono text-[11px] text-[#737373]">{stat.secondary}</dd>}
          </div>
        ))}
      </dl>
    </section>
  );
}
