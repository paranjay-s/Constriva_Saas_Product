/** The person's plans: name, where each one is, the quality it was built at, Open and Delete. */
import { TrashIcon } from '../../../components/ui/Icons';
import { jobName, qualityLabel, stageText } from '../plan3dLogic';
import type { Plan3dJob, Plan3dQuality } from '../plan3dSchemas';
import { LinkButton } from './Plan3dParts';

interface Plan3dJobListProps {
  jobs: readonly Plan3dJob[];
  /** The server's names of the build qualities; the built-in names are used without them. */
  qualities: readonly Plan3dQuality[];
  /** The job being deleted right now, if any. */
  deletingId: string | null;
  onDelete: (job: Plan3dJob) => void;
}

const FOCUS = 'focus:outline-none focus-visible:ring-2 focus-visible:ring-[#C5A77B]';

function dayText(createdAt: string | null): string | null {
  if (!createdAt) return null;
  const date = new Date(createdAt);
  return Number.isNaN(date.getTime()) ? null : date.toLocaleDateString();
}

export function Plan3dJobList({ jobs, qualities, deletingId, onDelete }: Plan3dJobListProps) {
  return (
    <ul className="flex flex-col gap-3">
      {jobs.map((job) => {
        const name = jobName(job);
        const quality = job.stage === 'done' ? qualityLabel(job.quality, qualities) : null;
        const facts = [stageText(job), quality && `${quality} quality`, dayText(job.created_at)].filter(
          (fact): fact is string => Boolean(fact),
        );
        const deleting = deletingId === job.job_id;
        return (
          <li
            key={job.job_id}
            className="flex flex-wrap items-center justify-between gap-3 rounded border border-[#303030] bg-[#141414] p-4"
          >
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-white">{name}</div>
              <div className="break-words font-mono text-xs text-[#737373]">{facts.join(' • ')}</div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <LinkButton to={`/3d/${encodeURIComponent(job.job_id)}`} label={`Open ${name}`}>
                Open
              </LinkButton>
              <button
                type="button"
                onClick={() => onDelete(job)}
                disabled={deletingId !== null}
                aria-label={`Delete ${name}`}
                aria-busy={deleting}
                title="Delete"
                className={`cursor-pointer rounded p-2 text-[#737373] transition-colors hover:text-[#FFB4AB] disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS}`}
              >
                <TrashIcon size={16} aria-hidden="true" />
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
