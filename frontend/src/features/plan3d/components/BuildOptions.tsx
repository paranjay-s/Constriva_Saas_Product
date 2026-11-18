/**
 * The options of a build, next to the review page: furnish the rooms, the quality, and the
 * Build button. The qualities are the server's own list: one that cannot be built is shown
 * disabled, with the server's reason.
 */
import { type ReactNode, useId } from 'react';
import { Button } from '../../../components/ui/Button';
import type { Plan3dQuality, Plan3dQualityId } from '../plan3dSchemas';
import { ErrorNotice, StatusNote } from './Plan3dParts';

interface BuildOptionsProps {
  /** null until the server's list has arrived. */
  qualities: readonly Plan3dQuality[] | null;
  /** Why the list could not be loaded. */
  qualitiesError: string | null;
  onRetryQualities: () => void;
  furnish: boolean;
  onFurnish: (furnish: boolean) => void;
  quality: Plan3dQualityId | null;
  onQuality: (quality: Plan3dQualityId) => void;
  /** The review page has loaded the plan, so it can be saved and built. */
  ready: boolean;
  /** The plan is being saved and the build started. */
  busy: boolean;
  /** Why the plan could not be opened, saved or built. */
  error: string | null;
  /** A way out of `error`, e.g. a button that opens the review page again. */
  errorAction?: ReactNode;
  onBuild: () => void;
  /** Shown under the Build button, e.g. a way back for someone who came to edit a built plan. */
  children?: ReactNode;
}

export function BuildOptions(props: BuildOptionsProps) {
  const { qualities, qualitiesError, furnish, quality, ready, busy, error } = props;
  const id = useId();
  const nothingAvailable = qualities !== null && !qualities.some((option) => option.available);

  return (
    <section aria-label="Build options" className="flex flex-col gap-6 rounded-lg border border-[#303030] bg-[#202020] p-5">
      <h2 className="font-display text-lg font-semibold text-white">Options</h2>

      <div className="flex items-start gap-3">
        <input
          id={`${id}-furnish`}
          type="checkbox"
          checked={furnish}
          disabled={busy}
          onChange={(e) => props.onFurnish(e.target.checked)}
          aria-describedby={`${id}-furnish-hint`}
          className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-[#C5A77B]"
        />
        <div className="flex min-w-0 flex-col gap-0.5">
          <label htmlFor={`${id}-furnish`} className="cursor-pointer text-sm font-semibold text-white">
            Furnish the rooms
          </label>
          <span id={`${id}-furnish-hint`} className="text-xs text-[#A6A6A6]">
            Adds furniture to the rooms of the 3D house.
          </span>
        </div>
      </div>

      <fieldset disabled={busy} className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0">
        <legend className="mb-2 p-0 text-xs font-semibold uppercase tracking-wider text-[#A6A6A6]">Quality</legend>
        {qualities === null && !qualitiesError && <StatusNote>Loading the quality options…</StatusNote>}
        {qualitiesError && (
          <ErrorNotice message={`The quality options could not be loaded. ${qualitiesError}`}>
            <Button variant="secondary" size="sm" onClick={props.onRetryQualities}>
              Retry
            </Button>
          </ErrorNotice>
        )}
        {(qualities ?? []).map((option) => {
          const selected = quality === option.id;
          return (
            <label
              key={option.id}
              className={`flex items-start gap-3 rounded border p-3 transition-colors ${
                selected ? 'border-[#C5A77B] bg-[#181818]' : 'border-[#303030] bg-[#141414]'
              } ${option.available ? 'cursor-pointer hover:border-[#444444]' : 'cursor-not-allowed'}`}
            >
              <input
                type="radio"
                name={`${id}-quality`}
                value={option.id}
                checked={selected}
                disabled={!option.available}
                onChange={() => props.onQuality(option.id)}
                aria-labelledby={`${id}-${option.id}-name`}
                aria-describedby={`${id}-${option.id}-hint`}
                className="mt-0.5 h-4 w-4 shrink-0 accent-[#C5A77B]"
              />
              <span className="flex min-w-0 flex-col gap-0.5">
                <span
                  id={`${id}-${option.id}-name`}
                  className={`text-sm font-semibold ${option.available ? 'text-white' : 'text-[#A6A6A6]'}`}
                >
                  {option.label}
                </span>
                <span id={`${id}-${option.id}-hint`} className="break-words text-xs text-[#A6A6A6]">
                  {option.description}
                  {!option.available && option.reason && (
                    <span className="mt-1 block text-[#E2C294]">Not available: {option.reason}</span>
                  )}
                </span>
              </span>
            </label>
          );
        })}
        {nothingAvailable && <StatusNote>No quality can be built right now.</StatusNote>}
      </fieldset>

      {error && <ErrorNotice message={error}>{props.errorAction}</ErrorNotice>}

      <div className="flex flex-col gap-3 border-t border-[#303030] pt-4">
        <Button
          variant="accent"
          size="lg"
          fullWidth
          onClick={props.onBuild}
          disabled={!ready || quality === null}
          isLoading={busy}
          aria-busy={busy}
        >
          Build 3D
        </Button>
        {busy ? (
          <StatusNote>Saving the plan and starting the build…</StatusNote>
        ) : (
          !ready && !error && <StatusNote>The plan is still loading. You can build once it is shown.</StatusNote>
        )}
        {props.children}
      </div>
    </section>
  );
}
