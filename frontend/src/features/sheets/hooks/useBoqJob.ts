/**
 * One BOQ run: upload the PDF, follow the job over SSE, then fetch the finished bill.
 *
 * The phase is derived, never stored, so it cannot disagree with the data:
 * idle -> uploading -> processing -> loading_result -> ready, or error from any step.
 *
 * A ready bill can be calculated again with other assumptions, any number of times. That
 * replaces the bill on screen only when it works; a failure leaves the bill as it is.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useJobEvents } from '../../floorplan';
import { BOQ_BASE, boqApi, boqErrorText } from '../boqApi';
import type { BoqAssumptionsInput, BoqResult } from '../boqSchemas';

export type BoqPhase = 'idle' | 'uploading' | 'processing' | 'loading_result' | 'ready' | 'error';

const BOQ_JOBS = { base: BOQ_BASE };
const JOB_FAILED = 'The bill of quantities could not be generated from this file.';
const NO_CHOICES: BoqAssumptionsInput = {};

export function useBoqJob() {
  const [uploading, setUploading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<BoqResult | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [resultAttempt, setResultAttempt] = useState(0);
  const [recalculating, setRecalculating] = useState(false);
  const [recalculateError, setRecalculateError] = useState<string | null>(null);
  const [assumptionsInput, setAssumptionsInput] = useState<BoqAssumptionsInput>(NO_CHOICES);
  const upload = useRef<AbortController | null>(null);
  const recalculation = useRef<AbortController | null>(null);

  const { events, latest, finished } = useJobEvents(jobId, BOQ_JOBS);
  const jobDone = finished && latest?.status === 'done';
  const jobFailed = finished && latest?.status === 'failed';

  // leaving the page cancels an upload or a recalculation that is still in flight
  useEffect(
    () => () => {
      upload.current?.abort();
      recalculation.current?.abort();
    },
    [],
  );

  /** Forget the recalculation in flight, its error and the choices: they belong to one bill. */
  const dropRecalculation = useCallback(() => {
    recalculation.current?.abort();
    recalculation.current = null;
    setRecalculating(false);
    setRecalculateError(null);
    setAssumptionsInput(NO_CHOICES);
  }, []);

  const start = useCallback(async (file: File) => {
    upload.current?.abort();
    dropRecalculation();
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
  }, [dropRecalculation]);

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

  const ready = result !== null;

  /**
   * The bill on screen again, calculated with `input`: the complete set of the person's
   * choices (a field left out means "the default"). The newest call wins: an older one
   * that is still in flight is aborted and its reply ignored.
   */
  const recalculate = useCallback(
    async (input: BoqAssumptionsInput) => {
      if (!jobId || !ready) return; // there is no bill to calculate again
      recalculation.current?.abort();
      const controller = new AbortController();
      recalculation.current = controller;
      setRecalculating(true);
      setRecalculateError(null);
      try {
        const bill = await boqApi.recalculate(jobId, input, controller.signal);
        if (controller.signal.aborted) return;
        setResult(bill);
        setAssumptionsInput(input);
      } catch (e) {
        if (!controller.signal.aborted) setRecalculateError(boqErrorText(e));
      } finally {
        if (!controller.signal.aborted) setRecalculating(false);
      }
    },
    [jobId, ready],
  );

  /** Back to the empty page; anything still running is dropped. */
  const reset = useCallback(() => {
    upload.current?.abort();
    upload.current = null;
    dropRecalculation();
    setUploading(false);
    setJobId(null);
    setResult(null);
    setRequestError(null);
  }, [dropRecalculation]);

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
    /** The choices the bill on screen was calculated with; empty until the person changes one. */
    assumptionsInput,
    recalculating,
    /** Why the last recalculation failed; the bill on screen is still the one before it. */
    recalculateError,
    start,
    retryResult,
    recalculate,
    reset,
  };
}
