/**
 * Review and options: the 3D builder's own review page in an iframe (the detected plan over
 * the drawing, which the person can correct), and next to it the options of the build.
 *
 * The review page has no Build button here. Building is: ask the page to save the plan
 * (window.postMessage), wait until it says it did, then start the build through the API.
 * A message is believed only when it comes from the API's origin, from this very iframe,
 * and names this job.
 */
import { type ReactNode, type RefObject, useEffect, useRef, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { useEmbedAccess } from '../hooks/useEmbedAccess';
import { embedOrigin, embedUrl, plan3dApi, plan3dErrorText } from '../plan3dApi';
import { defaultQuality } from '../plan3dLogic';
import {
  type Plan3dJob,
  type Plan3dQuality,
  type Plan3dQualityId,
  type Plan3dSaveRequest,
  plan3dFrameMessageSchema,
} from '../plan3dSchemas';
import { BuildOptions } from './BuildOptions';
import { ErrorNotice, StatusNote } from './Plan3dParts';

/** How long the review page gets to say that it saved the plan. */
export const SAVE_TIMEOUT_MS = 10_000;

const NOT_SAVED = 'The plan could not be saved.';
const SAVE_TIMED_OUT = 'The review page did not confirm that the plan was saved. Please try again.';
/** Which reader made the plan, as the person is told. The reader's own notice follows. */
const READER_TEXT: Record<string, string> = {
  ai: 'This plan was read by the AI plan reader, because the drawing could not be read directly. Check the walls, doors, windows and sizes before you build.',
  stored: 'This plan comes from your floor plan. Nothing was read from the drawing.',
  trace: 'This drawing could not be read. Trace the walls over the page and set the scale before you build.',
  manual: 'Draw the plan over the page and set the scale before you build.',
};

const ACCESS_EXPIRED =
  'This page has been open for too long and can no longer save the plan. Open the plan again (changes that were not built are lost), then build.';

interface ReviewOptions {
  /** The server's build qualities; null until they have arrived. */
  qualities: readonly Plan3dQuality[] | null;
  qualitiesError: string | null;
  onRetryQualities: () => void;
  /** The build was started: the job as the server now describes it. */
  onBuilt: (job: Plan3dJob) => void;
  /** Shown under the Build button. */
  children?: ReactNode;
}

interface ReviewPanelProps extends ReviewOptions {
  /** The review page's iframe (the step refreshes its token through it). */
  frame: RefObject<HTMLIFrameElement | null>;
  jobId: string;
  /** URL of the review page. */
  src: string;
  /** True once the token in `src` has run out. */
  hasExpired: () => boolean;
  /** Fetch a new URL and open the review page again. */
  onReopen: () => void;
}

function ReviewPanel(props: ReviewPanelProps) {
  const { jobId, src, qualities, hasExpired, onBuilt, frame } = props;
  /** Settles the save that is waiting for the review page's answer. */
  const pendingSave = useRef<((problem: string | null) => void) | null>(null);
  const [ready, setReady] = useState(false);
  const [pageProblem, setPageProblem] = useState<string | null>(null);
  /** Why the plan cannot be built yet, as the review page says; null when it can. */
  const [notBuildable, setNotBuildable] = useState<string | null>(null);
  const [reader, setReader] = useState<{ reader: string; notice: string } | null>(null);
  const [furnish, setFurnish] = useState(true);
  const [picked, setPicked] = useState<Plan3dQualityId | null>(null);
  const [busy, setBusy] = useState(false);
  const [buildError, setBuildError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const quality = picked ?? defaultQuality(qualities ?? []);

  useEffect(() => {
    const origin = embedOrigin();
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== origin) return;
      if (!frame.current || event.source !== frame.current.contentWindow) return;
      const message = plan3dFrameMessageSchema.safeParse(event.data);
      if (!message.success || message.data.job !== jobId) return;
      switch (message.data.type) {
        case 'ready':
          setReady(true);
          setPageProblem(null);
          setReader({ reader: message.data.reader ?? '', notice: message.data.notice ?? '' });
          setNotBuildable(message.data.buildable === false ? message.data.problem || 'The plan cannot be built yet.' : null);
          break;
        case 'buildable':
          setNotBuildable(message.data.buildable ? null : message.data.problem || 'The plan cannot be built yet.');
          break;
        case 'failed':
          setPageProblem(`The plan could not be opened for review. ${message.data.message}`.trim());
          break;
        case 'saved':
          pendingSave.current?.(message.data.ok ? null : message.data.error || NOT_SAVED);
          break;
      }
    };
    window.addEventListener('message', onMessage);
    return () => {
      window.removeEventListener('message', onMessage);
      pendingSave.current?.(NOT_SAVED); // the page is gone: nothing will answer any more
    };
  }, [jobId, frame]);

  /** Ask the review page to save the plan as it is now; resolves once it says it did. */
  const save = (furnishRooms: boolean) =>
    new Promise<void>((resolve, reject) => {
      const page = frame.current?.contentWindow;
      if (!page) {
        reject(new Error(NOT_SAVED));
        return;
      }
      const settle = (problem: string | null) => {
        clearTimeout(timer);
        pendingSave.current = null;
        if (problem === null) resolve();
        else reject(new Error(problem));
      };
      const timer = setTimeout(() => settle(SAVE_TIMED_OUT), SAVE_TIMEOUT_MS);
      pendingSave.current = settle;
      const request: Plan3dSaveRequest = { source: 'planto3d-host', type: 'save', furnish: furnishRooms };
      page.postMessage(request, embedOrigin());
    });

  const build = async () => {
    if (busy || !ready || notBuildable !== null || quality === null) return;
    if (hasExpired()) {
      setExpired(true);
      setBuildError(ACCESS_EXPIRED);
      return;
    }
    setBusy(true);
    setBuildError(null);
    try {
      await save(furnish);
      onBuilt(await plan3dApi.build(jobId, quality));
    } catch (e) {
      setBuildError(plan3dErrorText(e));
    } finally {
      setBusy(false);
    }
  };

  const readerText = reader ? READER_TEXT[reader.reader] : undefined;
  const readerNotice = reader?.notice && reader.notice !== readerText ? reader.notice : '';

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start">
      <div className="flex min-w-0 flex-col gap-3">
        {(readerText || readerNotice) && (
          <div role="note" aria-label="How this plan was read" className="rounded-xl border border-[#5A4A2E] bg-[#1E1A12] p-3 text-sm text-[#bff6fb]">
            {readerText && <p className="m-0">{readerText}</p>}
            {readerNotice && <p className="m-0 mt-1 break-words text-xs text-[#bff6fb]">{readerNotice}</p>}
          </div>
        )}
        <div className="h-[70vh] min-h-[420px] overflow-hidden rounded-[22px] border border-[#243041] bg-[#0b1019]">
          <iframe ref={frame} title="Review the detected plan" src={src} className="h-full w-full border-0" />
        </div>
      </div>
      <BuildOptions
        qualities={qualities}
        qualitiesError={props.qualitiesError}
        onRetryQualities={props.onRetryQualities}
        furnish={furnish}
        onFurnish={setFurnish}
        quality={quality}
        onQuality={setPicked}
        ready={ready && notBuildable === null}
        busy={busy}
        error={buildError ?? pageProblem ?? notBuildable}
        errorAction={
          expired && (
            <Button variant="secondary" size="sm" onClick={props.onReopen}>
              Open the plan again
            </Button>
          )
        }
        onBuild={() => void build()}
      >
        {props.children}
      </BuildOptions>
    </div>
  );
}

interface ReviewStepProps extends ReviewOptions {
  jobId: string;
  /** Kept in the page but out of sight while the build it started is running. */
  hidden: boolean;
}

export function ReviewStep({ jobId, hidden, ...options }: ReviewStepProps) {
  const frame = useRef<HTMLIFrameElement>(null);
  const embed = useEmbedAccess(jobId, frame);
  const reviewUrl = embed.access?.review_url ?? null;

  return (
    <section aria-label="Review the plan" hidden={hidden} className={hidden ? 'hidden' : 'flex flex-col gap-4'}>
      <div className="text-sm text-[#a3afbf]">
        Check the walls, doors, windows and room types that were detected, and correct them on the drawing. Then choose
        the options and build.
      </div>
      {embed.loading && <StatusNote>Opening the plan…</StatusNote>}
      {embed.error && (
        <ErrorNotice message={`The plan could not be opened for review. ${embed.error}`}>
          <Button variant="secondary" size="sm" onClick={embed.reload}>
            Retry
          </Button>
        </ErrorNotice>
      )}
      {embed.access && !reviewUrl && <ErrorNotice message="The server did not say where the review page of this plan is." />}
      {reviewUrl && (
        // a new URL is a new page: what was known about the old one (loaded, saving) is dropped with it
        <ReviewPanel
          key={reviewUrl}
          jobId={jobId}
          frame={frame}
          src={embedUrl(reviewUrl)}
          hasExpired={embed.hasExpired}
          onReopen={embed.reload}
          {...options}
        />
      )}
    </section>
  );
}
