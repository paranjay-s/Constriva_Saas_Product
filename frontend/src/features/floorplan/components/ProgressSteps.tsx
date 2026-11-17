/** Step 3: live progress of the generation job. */
import type { JobEvent } from '../schemas';

const STEPS = [
  { stage: 'feasibility', label: 'Checking the rooms fit the plot' },
  { stage: 'program', label: 'Sizing the rooms' },
  { stage: 'layout', label: 'Placing rooms' },
  { stage: 'checking', label: 'Checking walls, doors and sizes' },
  { stage: 'saving', label: 'Saving the plan' },
] as const;

const ORDER: string[] = ['queued', ...STEPS.map((s) => s.stage), 'done'];

export function ProgressSteps({ events, onRetry }: { events: JobEvent[]; onRetry: () => void }) {
  const latest = events[events.length - 1];
  const failed = latest?.status === 'failed';
  const reached = Math.max(0, ...events.filter((e) => e.stage !== 'failed').map((e) => ORDER.indexOf(e.stage)));
  const pct = latest?.progress ?? 0;

  return (
    <section aria-live="polite" className="flex flex-col gap-4">
      <div>
        <div className="mb-1 flex justify-between text-xs text-[#9AA3B2]">
          <span>{failed ? 'Could not make a plan' : latest?.detail || 'Starting…'}</span>
          <span>{pct}%</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-[#23272F]" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div
            className={`h-full transition-all duration-500 ${failed ? 'bg-[#E5484D]' : 'bg-[#C5A77B]'}`}
            style={{ width: `${Math.max(pct, 3)}%` }}
          />
        </div>
      </div>

      <ol className="space-y-2">
        {STEPS.map((s) => {
          const idx = ORDER.indexOf(s.stage);
          const state = idx < reached ? 'done' : idx === reached && !failed ? 'active' : idx === reached && failed ? 'failed' : 'todo';
          return (
            <li key={s.stage} className="flex items-center gap-2.5 text-sm">
              <span
                className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
                  state === 'done'
                    ? 'bg-[#2E7D4F] text-white'
                    : state === 'active'
                      ? 'border-2 border-[#C5A77B] border-t-transparent animate-spin'
                      : state === 'failed'
                        ? 'bg-[#E5484D] text-white'
                        : 'border border-[#3A404B]'
                }`}
                aria-hidden
              >
                {state === 'done' ? '✓' : state === 'failed' ? '!' : ''}
              </span>
              <span className={state === 'todo' ? 'text-[#5C6370]' : 'text-[#D5DAE1]'}>{s.label}</span>
            </li>
          );
        })}
      </ol>

      {failed && (
        <div className="rounded-md border border-[#E5484D]/40 bg-[#E5484D]/10 p-3 text-sm text-[#FFDAD6]">
          <p>{latest.error}</p>
          {latest.options.length > 0 && (
            <>
              <p className="mt-2 font-medium">You could:</p>
              <ul className="list-disc pl-5">
                {latest.options.map((o) => (
                  <li key={o}>{o}</li>
                ))}
              </ul>
            </>
          )}
          <button type="button" onClick={onRetry} className="mt-3 cursor-pointer text-[#C5A77B] underline">
            Change the brief and try again
          </button>
        </div>
      )}
    </section>
  );
}
