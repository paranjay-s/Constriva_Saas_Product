/**
 * Step 0: every floor plan is made inside one of the user's projects, so it shows up in
 * their project list. Choose an existing project or create a new one first.
 */
import type { Project } from '../../../types';

export const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** A project that really exists in the user's account (not a local placeholder). */
export function isSavedProject(p: Project | null | undefined, projects: Project[]): p is Project {
  return Boolean(p && UUID_RE.test(p.id) && projects.some((x) => x.id === p.id));
}

interface Props {
  projects: Project[];
  loading: boolean;
  error?: string | null;
  onChoose: (project: Project) => void;
  onCreate: () => void;
  onRetry: () => void;
}

export function ProjectGate({ projects, loading, error, onChoose, onCreate, onRetry }: Props) {
  const saved = projects.filter((p) => UUID_RE.test(p.id));
  return (
    <section aria-label="Choose a project" className="flex flex-col gap-4">
      <div>
        <h2 className="text-sm font-semibold">Choose a project first</h2>
        <p className="mt-1 text-xs text-[#7D8594]">
          The floor plan is saved inside the project, so you can find it again on your home page.
        </p>
      </div>

      <button
        type="button"
        onClick={onCreate}
        className="cursor-pointer rounded-md bg-[#C5A77B] px-3 py-2.5 text-sm font-semibold text-[#101010] hover:bg-[#d6bb92]"
      >
        + Create a new project
      </button>

      {loading && saved.length === 0 && <p className="text-sm text-[#7D8594]">Loading your projects…</p>}
      {error && (
        <div role="alert" className="rounded-md border border-[#E5484D]/40 bg-[#E5484D]/10 p-3 text-sm text-[#FFDAD6]">
          {error}{' '}
          <button type="button" onClick={onRetry} className="cursor-pointer underline">
            Try again
          </button>
        </div>
      )}
      {!loading && !error && saved.length === 0 && (
        <p className="text-sm text-[#9AA3B2]">You have no projects yet. Create one to start.</p>
      )}

      {saved.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-[11px] uppercase tracking-wider text-[#7D8594]">Or use an existing project</p>
          <ul className="flex max-h-[50vh] flex-col gap-1.5 overflow-y-auto pr-1">
            {saved.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => onChoose(p)}
                  className="w-full cursor-pointer rounded-md border border-[#2A2F38] bg-[#0F1115] px-3 py-2 text-left hover:border-[#C5A77B]"
                >
                  <span className="block truncate text-sm text-white">{p.name}</span>
                  <span className="text-[11px] text-[#7D8594]">
                    {p.type} · {new Date(p.createdAt).toLocaleDateString()}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
