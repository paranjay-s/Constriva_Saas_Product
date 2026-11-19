/** The six steps from a PDF to a walkthrough, with the one a job is in marked. */
import { CheckIcon } from '../../../components/ui/Icons';
import { PLAN3D_STEPS, type Plan3dStepState, type Plan3dView, stepStates } from '../plan3dLogic';

const STATE_TEXT: Record<Plan3dStepState, string> = {
  done: 'done',
  active: 'in progress',
  failed: 'failed',
  todo: 'not started',
};

const MARK: Record<Plan3dStepState, string> = {
  done: 'border-[#10B981] bg-[#102A1A] text-[#A7F3D0]',
  active: 'border-[#7ce8f2] bg-[#7ce8f2] text-[#04060a]',
  failed: 'border-[#FFB4AB] bg-[#351010] text-[#FFB4AB]',
  todo: 'border-[#243041] text-[#8b97a8]',
};

export function Plan3dStepper({ view }: { view: Plan3dView }) {
  const states = stepStates(view);
  const current = states.findIndex((state) => state === 'active' || state === 'failed');

  return (
    <ol aria-label="Steps" className="flex flex-wrap items-center gap-x-4 gap-y-2">
      {PLAN3D_STEPS.map((step, index) => {
        const state = states[index];
        return (
          <li key={step.id} aria-current={index === current ? 'step' : undefined} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border font-mono text-[10px] font-bold ${MARK[state]}`}
            >
              {state === 'done' ? <CheckIcon size={10} /> : index + 1}
            </span>
            <span
              className={`font-mono text-[11px] uppercase tracking-wider ${state === 'todo' ? 'text-[#8b97a8]' : 'text-white'}`}
            >
              {step.label}
              <span className="sr-only"> ({STATE_TEXT[state]})</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
