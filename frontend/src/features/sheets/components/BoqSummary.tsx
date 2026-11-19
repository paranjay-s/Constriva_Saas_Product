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
            className={`flex flex-col gap-0.5 rounded-xl border border-[#243041] bg-[#0b1019] p-3 ${
              index === 0 ? 'col-span-2 sm:col-span-1' : ''
            }`}
          >
            <dt className="font-mono text-[10px] uppercase tracking-wider text-[#a3afbf]">{stat.label}</dt>
            <dd className="m-0 font-mono text-lg font-bold text-[#7ce8f2]">{stat.value}</dd>
            {stat.secondary && <dd className="m-0 font-mono text-[11px] text-[#8b97a8]">{stat.secondary}</dd>}
          </div>
        ))}
      </dl>
    </section>
  );
}
