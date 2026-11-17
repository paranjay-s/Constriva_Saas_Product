/**
 * Follow a generation job's progress over SSE.
 *
 * EventSource cannot send the Bearer token, so the stream is read with fetch(). If the
 * stream breaks (proxy, network), the hook falls back to polling GET /jobs/{id}, so the
 * UI never gets stuck. The server replays all past events on connect, so nothing is lost.
 */
import { useEffect, useState } from 'react';
import { API_BASE_URL, apiRequest } from '../../../lib/api';
import { FLOORPLAN_BASE, authHeaders, floorplanApi } from '../api';
import { type JobEvent, type JobState, jobEventSchema, jobStateSchema } from '../schemas';

export interface SseMessage {
  event: string;
  data: string;
}

/** Split an SSE text buffer into complete messages; returns them and the unfinished rest. */
export function parseSse(buffer: string): { messages: SseMessage[]; rest: string } {
  const messages: SseMessage[] = [];
  const blocks = buffer.replace(/\r\n/g, '\n').split('\n\n');
  const rest = blocks.pop() ?? '';
  for (const block of blocks) {
    let event = 'message';
    const data: string[] = [];
    for (const line of block.split('\n')) {
      if (line.startsWith(':')) continue; // keep-alive comment
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
    }
    if (data.length) messages.push({ event, data: data.join('\n') });
  }
  return { messages, rest };
}

export interface JobProgress {
  events: JobEvent[];
  latest: JobEvent | null;
  finished: boolean;
}

const POLL_MS = 1000;

function sameEvent(a: JobEvent, b: JobEvent): boolean {
  return a.stage === b.stage && a.detail === b.detail && a.progress === b.progress && a.status === b.status;
}

export interface JobSource {
  /** API base whose /jobs/{id} and /jobs/{id}/events endpoints are followed. */
  base: string;
  /** Polling fallback; defaults to GET {base}/jobs/{id}. */
  fetchJob?: (jobId: string) => Promise<JobState>;
}

const FLOORPLAN_JOBS: JobSource = { base: FLOORPLAN_BASE, fetchJob: (id) => floorplanApi.job(id) };

/** Other features (e.g. the material finder) pass their own API base. */
export function useJobEvents(jobId: string | null, source: JobSource = FLOORPLAN_JOBS): JobProgress {
  const { base } = source;
  const fetchJob =
    source.fetchJob ??
    (async (id: string) => jobStateSchema.parse(await apiRequest(`${base}/jobs/${encodeURIComponent(id)}`)));
  // events are stored with the job they belong to, so a new job starts empty without a reset
  const [state, setState] = useState<{ jobId: string | null; events: JobEvent[] }>({ jobId: null, events: [] });

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    const live = { finished: false, poll: undefined as ReturnType<typeof setTimeout> | undefined };

    const accept = (ev: JobEvent) => {
      setState((prev) => {
        const events = prev.jobId === jobId ? prev.events : [];
        return events.some((p) => sameEvent(p, ev)) ? prev : { jobId, events: [...events, ev] };
      });
      if (ev.status === 'done' || ev.status === 'failed') live.finished = true;
    };

    const poll = async () => {
      if (controller.signal.aborted || live.finished) return;
      try {
        const st = await fetchJob(jobId);
        st.events.forEach(accept);
      } catch {
        // keep trying; the job may simply be slow
      }
      if (!live.finished && !controller.signal.aborted) live.poll = setTimeout(poll, POLL_MS);
    };

    const stream = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}${base}/jobs/${encodeURIComponent(jobId)}/events`, {
          headers: authHeaders(),
          signal: controller.signal,
        });
        if (!res.ok || !res.body) throw new Error(`stream ${res.status}`);
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parsed = parseSse(buffer);
          buffer = parsed.rest;
          for (const m of parsed.messages) {
            if (m.event === 'end') return;
            if (m.event !== 'progress') continue;
            const ev = jobEventSchema.safeParse(JSON.parse(m.data));
            if (ev.success) accept(ev.data);
          }
        }
        if (!live.finished) void poll();
      } catch {
        if (!controller.signal.aborted) void poll();
      }
    };

    void stream();
    return () => {
      controller.abort();
      if (live.poll) clearTimeout(live.poll);
    };
    // fetchJob is derived from base; following a new base restarts the stream
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, base]);

  const events = state.jobId === jobId ? state.events : [];
  const latest = events.length ? events[events.length - 1] : null;
  return { events, latest, finished: latest?.status === 'done' || latest?.status === 'failed' };
}
