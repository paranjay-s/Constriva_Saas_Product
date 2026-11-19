/** Progress of the detection or of the build: what is happening, a bar, and what is known about the wait. */
import { percent } from '../plan3dLogic';

interface Plan3dProgressProps {
  title: string;
  /** Names the bar for screen readers, e.g. "Build progress". */
  label: string;
  /** 0 to 100; null when there is no figure yet (e.g. waiting in the queue). */
  progress: number | null;
  /** What the server says it is doing. */
  message: string;
  /** Short facts shown under the bar: time left, place in the queue, quality. */
  facts?: readonly string[];
}

export function Plan3dProgress({ title, label, progress, message, facts = [] }: Plan3dProgressProps) {
  const figure = progress === null ? null : percent(progress);

  return (
    <section aria-label={label} className="flex flex-col gap-6 py-4">
      <h2 className="text-center text-[19px] font-medium text-white">{title}</h2>

      <div className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between gap-3 text-sm text-[#a3afbf]">
          <span role="status" aria-live="polite" className="min-w-0 break-words">
            {message}
          </span>
          {figure !== null && <span className="font-mono text-xs font-bold text-[#7ce8f2]">{figure}%</span>}
        </div>
        <div
          role="progressbar"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={figure ?? undefined}
          aria-valuetext={figure === null ? message : `${figure}%`}
          className="h-2 w-full overflow-hidden rounded-full border border-[#243041] bg-[#04060a]"
        >
          <div
            className={`h-full bg-[#7ce8f2] transition-all duration-500 ease-out ${figure === null ? 'animate-pulse' : ''}`}
            style={{ width: `${figure === null ? 12 : Math.max(figure, 3)}%` }}
          />
        </div>
      </div>

      {facts.length > 0 && (
        <ul className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 font-mono text-xs text-[#a3afbf]">
          {facts.map((fact) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
