/**
 * One BOQ run: upload the PDF, follow the job over SSE, then fetch the finished bill.
 *
 * The phase is derived, never stored, so it cannot disagree with the data:
 * idle -> uploading -> processing -> loading_result -> ready, or error from any step.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useJobEvents } from '../../floorplan';
import { BOQ_BASE, boqApi, boqErrorText } from '../boqApi';
import type { BoqResult } from '../boqSchemas';

export type BoqPhase = 'idle' | 'uploading' | 'processing' | 'loading_result' | 'ready' | 'error';

const BOQ_JOBS = { base: BOQ_BASE };
const JOB_FAILED = 'The bill of quantities could not be generated from this file.';

export function useBoqJob() {
  const [uploading, setUploading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<BoqResult | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [resultAttempt, setResultAttempt] = useState(0);
  const upload = useRef<AbortController | null>(null);

  const { events, latest, finished } = useJobEvents(jobId, BOQ_JOBS);
  const jobDone = finished && latest?.status === 'done';
  const jobFailed = finished && latest?.status === 'failed';

  // leaving the page cancels an upload that is still in flight
  useEffect(() => () => upload.current?.abort(), []);

  const start = useCallback(async (file: File) => {
    upload.current?.abort();
    const controller = new AbortController();
    upload.current = controller;
    setResult(null);
    setRequestError(null);
    setJobId(null);
    setUploading(true);
    try {
      const created = await boqApi.start(file, controller.signal);
      if (!controller.signal.aborted) setJobId(created.job_id);
    } catch (e) {
      if (!controller.signal.aborted) setRequestError(boqErrorText(e));
    } finally {
      if (!controller.signal.aborted) setUploading(false);
    }
  }, []);

  // the job is done: fetch the bill (again when the person asks to retry)
  useEffect(() => {
    if (!jobId || !jobDone) return;
    let cancelled = false;
    boqApi
      .result(jobId)
      .then((bill) => {
        if (!cancelled) setResult(bill);
      })
      .catch((e: unknown) => {
        if (!cancelled) setRequestError(boqErrorText(e));
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, jobDone, resultAttempt]);

  const retryResult = useCallback(() => {
    setRequestError(null);
    setResultAttempt((n) => n + 1);
  }, []);

  /** Back to the empty page; anything still running is dropped. */
  const reset = useCallback(() => {
    upload.current?.abort();
    upload.current = null;
    setUploading(false);
    setJobId(null);
    setResult(null);
    setRequestError(null);
  }, []);

  const error = requestError ?? (jobFailed ? latest?.error || latest?.detail || JOB_FAILED : null);
  const phase: BoqPhase = result
    ? 'ready'
    : error
      ? 'error'
      : uploading
        ? 'uploading'
        : jobId
          ? jobDone
            ? 'loading_result'
            : 'processing'
          : 'idle';

  return {
    phase,
    events,
    result,
    error,
    /** True when the job finished but its result could not be fetched: no need to upload again. */
    canRetryResult: requestError !== null && jobDone && !result,
    start,
    retryResult,
    reset,
  };
}
