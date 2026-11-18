/**
 * The signed URLs of the embedded pages, fetched once when the step that shows an iframe
 * is entered (the component mounts), not on every status update: changing an iframe's
 * `src` reloads the page inside it. `reload` fetches them again, on purpose.
 */
import { type RefObject, useCallback, useEffect, useState } from 'react';
import { embedOrigin, plan3dApi, plan3dErrorText } from '../plan3dApi';
import type { Plan3dEmbed } from '../plan3dSchemas';

interface Loaded {
  /** The request this answer belongs to. */
  key: string;
  access: Plan3dEmbed | null;
  error: string | null;
  /** When the URLs were issued (ms), to know when their token has run out. */
  at: number;
}

/** Share of a token's lifetime after which a fresh one is fetched and handed to the open page. */
export const REFRESH_AT = 0.75;

/** `jobId` null asks for the furniture models page, which has no job. With `frame`, a fresh token is
 *  fetched before the current one runs out and posted to the page in that iframe (which takes it in
 *  place, without reloading). */
export function useEmbedAccess(jobId: string | null, frame?: RefObject<HTMLIFrameElement | null>) {
  const [refreshedAt, setRefreshedAt] = useState<number | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const key = `${jobId ?? ''}#${attempt}`;

  useEffect(() => {
    const controller = new AbortController();
    const request = jobId ? plan3dApi.embed(jobId, controller.signal) : plan3dApi.furnitureEmbed(controller.signal);
    request.then(
      (access) => {
        if (!controller.signal.aborted) setLoaded({ key, access, error: null, at: Date.now() });
      },
      (e: unknown) => {
        if (!controller.signal.aborted) setLoaded({ key, access: null, error: plan3dErrorText(e), at: Date.now() });
      },
    );
    return () => controller.abort();
  }, [jobId, key]);

  const current = loaded?.key === key ? loaded : null;
  const access = current?.access ?? null;
  const issuedAt = Math.max(current?.at ?? 0, refreshedAt ?? 0);
  const lifetimeMs = (access?.expires_in ?? 0) * 1000;

  useEffect(() => {
    if (!frame || !access || lifetimeMs <= 0) return;
    const timer = setTimeout(() => {
      const request = jobId ? plan3dApi.embed(jobId) : plan3dApi.furnitureEmbed();
      request.then(
        (fresh) => {
          frame.current?.contentWindow?.postMessage({ source: 'planto3d-host', type: 'token', base: fresh.base_url }, embedOrigin());
          setRefreshedAt(Date.now());
        },
        () => {
          // no fresh token now: the page keeps its own until it runs out, then offers to open again
        },
      );
    }, Math.max(1000, lifetimeMs * REFRESH_AT - (Date.now() - issuedAt)));
    return () => clearTimeout(timer);
  }, [frame, access, jobId, lifetimeMs, issuedAt]);

  /** True once the token in the URLs has run out: the page inside the iframe can no longer save or load. */
  const hasExpired = useCallback(() => lifetimeMs > 0 && Date.now() > issuedAt + lifetimeMs, [issuedAt, lifetimeMs]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  return { access, error: current?.error ?? null, loading: current === null, hasExpired, reload };
}
