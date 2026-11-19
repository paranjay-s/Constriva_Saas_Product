/** Warnings raised while the bill was calculated. Hidden when there are none. */
import { useId, useState } from 'react';
import { AlertCircleIcon } from '../../../components/ui/Icons';

/** More warnings than this are folded behind a "show all" button. */
const ALWAYS_SHOWN = 3;

export function BoqWarnings({ warnings }: { warnings: readonly string[] }) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  if (warnings.length === 0) return null;

  const collapsible = warnings.length > ALWAYS_SHOWN;
  const shown = collapsible && !open ? warnings.slice(0, ALWAYS_SHOWN) : warnings;

  return (
    <section
      aria-label="Warnings"
      className="flex items-start gap-3 rounded-xl border border-[#7ce8f2]/40 bg-[#7ce8f2]/10 p-4 text-[#bff6fb]"
    >
      <AlertCircleIcon size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <h2 className="text-sm font-semibold">
          {warnings.length === 1 ? '1 warning' : `${warnings.length} warnings`}
        </h2>
        <ul id={listId} className="flex flex-col gap-1.5 text-xs leading-relaxed text-[#eef3f8]/85">
          {shown.map((warning, index) => (
            <li key={index} className="flex gap-2">
              <span aria-hidden="true" className="text-[#7ce8f2]">
                •
              </span>
              <span className="min-w-0 break-words">{warning}</span>
            </li>
          ))}
        </ul>
        {collapsible && (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={listId}
            onClick={() => setOpen((o) => !o)}
            className="cursor-pointer self-start rounded-xl text-xs font-semibold text-[#7ce8f2] underline underline-offset-2 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-[#7ce8f2]"
          >
            {open ? 'Show fewer warnings' : `Show all ${warnings.length} warnings`}
          </button>
        )}
      </div>
    </section>
  );
}
