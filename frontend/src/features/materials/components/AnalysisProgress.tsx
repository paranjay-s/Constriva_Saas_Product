/** Live progress of a photo analysis (or plan reading) job. */
import { MATERIAL_STAGES } from '../schemas';

export interface ProgressEvent {
  stage: string;
  status: string;
  detail: string;
  progress: number;
  error?: string | null;
}

const ORDER: string[] = ['queued', ...MATERIAL_STAGES.map((s) => s.stage), 'saving', 'done'];

export function AnalysisProgress({ events, onRetry }: { events: ProgressEvent[]; onRetry?: () => void }) {
  const latest = events[events.length - 1];
  const failed = latest?.status === 'failed';
  const reached = Math.max(0, ...events.filter((e) => e.stage !== 'failed').map((e) => ORDER.indexOf(e.stage)));
  const pct = latest?.progress ?? 0;
  return (
    <section aria-live="polite" className="space-y-4">
      <div>
        <div className="mb-1 flex justify-between text-xs text-[#9AA3B2]">
          <span>{failed ? latest?.error || 'The analysis failed' : latest?.detail || 'Starting…'}</span>
          <span>{pct}%</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-[#23272F]" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div className={`h-full transition-all duration-500 ${failed ? 'bg-[#E5484D]' : 'bg-[#C5A77B]'}`} style={{ width: `${Math.max(pct, 3)}%` }} />
        </div>
      </div>
      <ol className="space-y-2">
        {MATERIAL_STAGES.map((s) => {
          const idx = ORDER.indexOf(s.stage);
          const state = idx < reached ? 'done' : idx === reached ? (failed ? 'failed' : 'active') : 'todo';
          return (
            <li key={s.stage} className="flex items-center gap-2.5 text-sm">
              <span
                aria-hidden
                className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
                  state === 'done'
                    ? 'bg-[#2E7D4F] text-white'
                    : state === 'active'
                      ? 'animate-spin border-2 border-[#C5A77B] border-t-transparent'
                      : state === 'failed'
                        ? 'bg-[#E5484D] text-white'
                        : 'border border-[#3A404B]'
                }`}
              >
                {state === 'done' ? '✓' : state === 'failed' ? '!' : ''}
              </span>
              <span className={state === 'todo' ? 'text-[#5C6370]' : 'text-[#D5DAE1]'}>{s.label}</span>
            </li>
          );
        })}
      </ol>
      {failed && onRetry && (
        <button type="button" onClick={onRetry} className="rounded-md border border-[#3A404B] px-3 py-1.5 text-xs text-white hover:border-[#C5A77B]">
          Try again
        </button>
      )}
    </section>
  );
}
