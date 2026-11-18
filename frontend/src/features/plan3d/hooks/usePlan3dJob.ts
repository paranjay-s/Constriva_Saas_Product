/**
 * One 3D job, followed by asking for its status again while it is being worked on.
 *
 * The status is asked for every PLAN3D_POLL_MS while the stage is uploaded, detecting,
 * queued or building. It stops when the plan is detected, the house is done or the job
 * failed, and when the page lets go. A request that fails in between is tried again: the
 * job may simply be slow, or the connection briefly gone.
 */
import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '../../../lib/api';
import { isNotFound, plan3dApi, plan3dErrorText } from '../plan3dApi';
import { isActiveStage } from '../plan3dLogic';
import type { Plan3dJob } from '../plan3dSchemas';

export const PLAN3D_POLL_MS = 1500;

interface JobState {
  /** The job this state belongs to, so another job starts empty without a reset. */
  jobId: string;
  job: Plan3dJob | null;
  notFound: boolean;
  /** Why the job could not be loaded at all. */
  error: string | null;
  /** The last request failed; the status on screen may be old. */
  stale: boolean;
}

const emptyState = (jobId: string): JobState => ({ jobId, job: null, notFound: false, error: null, stale: false });

/** The person has to act (sign in again, or go elsewhere): asking again will not help. */
function isFinal(e: unknown): boolean {
  return e instanceof ApiError && (e.status === 401 || e.status === 403 || e.status === 404);
}

export function usePlan3dJob(jobId: string) {
  const [stored, setStored] = useState<JobState>(() => emptyState(jobId));
  const [attempt, setAttempt] = useState(0);
  const state = stored.jobId === jobId ? stored : emptyState(jobId);
  const { job } = state;

  const loaded = job !== null;
  const waiting = !loaded && !state.notFound && state.error === null;
  const following = waiting || (loaded && isActiveStage(job.stage));

  useEffect(() => {
    if (!following) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let known = loaded;

    const ask = async () => {
      try {
        const next = await plan3dApi.job(jobId, controller.signal);
        if (controller.signal.aborted) return;
        known = true;
        setStored({ ...emptyState(jobId), job: next });
        if (isActiveStage(next.stage)) timer = setTimeout(ask, PLAN3D_POLL_MS);
      } catch (e) {
        if (controller.signal.aborted) return;
        if (isNotFound(e)) {
          setStored({ ...emptyState(jobId), notFound: true });
        } else if (!known || isFinal(e)) {
          setStored((prev) => ({ ...(prev.jobId === jobId ? prev : emptyState(jobId)), error: plan3dErrorText(e) }));
        } else {
          setStored((prev) => (prev.jobId === jobId ? { ...prev, stale: true } : prev));
          timer = setTimeout(ask, PLAN3D_POLL_MS);
        }
      }
    };

    // a job that is already on screen is asked about again after the usual wait
    if (known) timer = setTimeout(ask, PLAN3D_POLL_MS);
    else void ask();

    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
    };
    // `loaded` only decides how the first request of a run is timed; a run is not restarted for it
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, following, attempt]);

  /** Put a status the server just returned (e.g. from starting a build) on screen. */
  const setJob = useCallback((next: Plan3dJob) => setStored({ ...emptyState(next.job_id), job: next }), []);

  /** Ask again after the job could not be loaded. */
  const retry = useCallback(() => {
    setStored(emptyState(jobId));
    setAttempt((n) => n + 1);
  }, [jobId]);

  return {
    job,
    loading: waiting,
    notFound: state.notFound,
    /** Set when the job cannot be shown (or followed any further); `job` may still be the last one seen. */
    error: state.error,
    stale: state.stale,
    setJob,
    retry,
  };
}
