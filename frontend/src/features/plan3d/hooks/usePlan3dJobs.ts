/** The person's 3D jobs, newest first: all of them, or those of one project. */
import { useCallback, useEffect, useState } from 'react';
import { plan3dApi, plan3dErrorText } from '../plan3dApi';
import type { Plan3dJob } from '../plan3dSchemas';

interface Loaded {
  /** The request this answer belongs to. */
  key: string;
  jobs: Plan3dJob[] | null;
  error: string | null;
}

/**
 * `projectId` null lists every job. Nothing is asked while `enabled` is false (the caller
 * does not know yet which project to ask for).
 */
export function usePlan3dJobs(projectId: string | null, enabled: boolean) {
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const key = `${projectId ?? ''}#${attempt}`;

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    plan3dApi.list(projectId, controller.signal).then(
      (jobs) => {
        if (!controller.signal.aborted) setLoaded({ key, jobs, error: null });
      },
      (e: unknown) => {
        if (!controller.signal.aborted) setLoaded({ key, jobs: null, error: plan3dErrorText(e) });
      },
    );
    return () => controller.abort();
  }, [enabled, projectId, key]);

  const current = loaded?.key === key ? loaded : null;

  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  /** Take a deleted job off the list without asking for the list again. */
  const drop = useCallback((jobId: string) => {
    setLoaded((prev) => (prev?.jobs ? { ...prev, jobs: prev.jobs.filter((job) => job.job_id !== jobId) } : prev));
  }, []);

  return { jobs: current?.jobs ?? null, error: current?.error ?? null, loading: current === null, reload, drop };
}
