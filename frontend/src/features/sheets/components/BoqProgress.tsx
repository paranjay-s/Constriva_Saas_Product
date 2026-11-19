/** Live progress of a BOQ run as three steps: Uploading, Parsing, Calculating. */
import { CheckIcon } from '../../../components/ui/Icons';
import { type BoqStepState, stepStates } from '../boqLogic';
import { BOQ_STEPS } from '../boqSchemas';

export interface BoqProgressEvent {
  stage: string;
  detail: string;
  progress: number;
}

interface BoqProgressProps {
  /** True while the PDF itself is still being sent (no job yet). */
  uploading: boolean;
  events: readonly BoqProgressEvent[];
  fileName?: string | null;
  /** The job is done and the bill is being fetched. */
  loadingResult?: boolean;
}

const STATE_TEXT: Record<BoqStepState, string> = { done: 'done', active: 'in progress', todo: 'not started' };

export function BoqProgress({ uploading, events, fileName, loadingResult = false }: BoqProgressProps) {
  const latest = events.length > 0 ? events[events.length - 1] : null;
  const states = stepStates({ uploading, stages: events.map((e) => e.stage) });
  // no figure while the file is being sent: the browser does not report upload progress
  const percent = uploading || !latest ? null : Math.min(100, Math.max(0, Math.round(latest.progress)));
  const detail = loadingResult
    ? 'Loading the bill of quantities…'
    : uploading
      ? 'Uploading the PDF…'
      : latest?.detail || 'Starting…';

  return (
    <section aria-label="Progress" className="flex flex-col gap-6 py-4">
      <div className="flex flex-col gap-1.5 text-center">
        <h2 className="text-[19px] font-medium text-white">Preparing your bill of quantities</h2>
        {fileName && <div className="truncate font-mono text-xs text-[#8b97a8]">{fileName}</div>}
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between gap-3 text-sm text-[#a3afbf]">
          <span role="status" aria-live="polite">
            {detail}
          </span>
          {percent !== null && <span className="font-mono text-xs font-bold text-[#7ce8f2]">{percent}%</span>}
        </div>
        <div
          role="progressbar"
          aria-label="BOQ progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent ?? undefined}
          aria-valuetext={percent === null ? detail : `${percent}%`}
          className="h-2 w-full overflow-hidden rounded-full border border-[#243041] bg-[#04060a]"
        >
          <div
            className={`h-full bg-[#7ce8f2] transition-all duration-500 ease-out ${percent === null ? 'animate-pulse' : ''}`}
            style={{ width: `${percent === null ? 12 : Math.max(percent, 3)}%` }}
          />
        </div>
      </div>

      <ol className="flex flex-col gap-3">
        {BOQ_STEPS.map((step, index) => {
          const state = states[index];
          return (
            <li key={step.id} aria-current={state === 'active' ? 'step' : undefined} className="flex items-center gap-3">
              <span
                aria-hidden="true"
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
                  state === 'done'
                    ? 'border border-[#10B981] bg-[#102A1A] text-[#A7F3D0]'
                    : state === 'active'
                      ? 'animate-spin border-2 border-[#7ce8f2] border-t-transparent'
                      : 'border border-[#243041]'
                }`}
              >
                {state === 'done' && <CheckIcon size={12} />}
              </span>
              <span className="flex flex-col">
                <span className={`text-sm font-semibold ${state === 'todo' ? 'text-[#8b97a8]' : 'text-white'}`}>
                  {step.label}
                  <span className="sr-only"> ({STATE_TEXT[state]})</span>
                </span>
                <span className="text-xs text-[#8b97a8]">{step.hint}</span>
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
