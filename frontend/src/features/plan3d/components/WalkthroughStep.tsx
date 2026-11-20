/**
 * The built house: the 3D builder's own walkthrough page in an iframe (walk, top view, map,
 * screenshot, recording), and what can be done with the house from here.
 */
import { useEffect, useRef, useState } from "react";
import { Button } from "../../../components/ui/Button";
import {
  IconDownload,
  IconMaximize,
  TrashIcon,
} from "../../../components/ui/Icons";
import { useEmbedAccess } from "../hooks/useEmbedAccess";
import {
  embedUrl,
  jobFileUrl,
  plan3dApi,
  plan3dErrorText,
  startDownload,
} from "../plan3dApi";
import { durationText, jobName, qualityLabel } from "../plan3dLogic";
import type { Plan3dJob, Plan3dQuality } from "../plan3dSchemas";
import { ErrorNotice, LinkButton, StatusNote } from "./Plan3dParts";

interface WalkthroughStepProps {
  job: Plan3dJob;
  /** The server's names of the build qualities; the built-in names are used without them. */
  qualities: readonly Plan3dQuality[];
  /** Show the review page and the options again, to change the plan and build it once more. */
  onEdit: () => void;
  /** The job was deleted. */
  onDeleted: () => void;
  /** A video tour was asked for: the job as the server now reports it (queued). */
  onTourStarted?: (job: Plan3dJob) => void;
}

const TOUR_NAMES = { high: "High (1080p)", ultra: "Ultra (1080p, path traced)" } as const;
const STILL_NAMES = { evening: "Evening", day: "Daylight" } as const;

export function WalkthroughStep({
  job,
  qualities,
  onEdit,
  onDeleted,
  onTourStarted,
}: WalkthroughStepProps) {
  const jobId = job.job_id;
  const frame = useRef<HTMLIFrameElement>(null);
  const embed = useEmbedAccess(jobId, frame);
  const box = useRef<HTMLDivElement>(null);
  const onPage = useRef(true);
  const [busy, setBusy] = useState<"export" | "delete" | "tour" | "stills" | "share" | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const walkthroughUrl = embed.access?.walkthrough_url ?? null;

  useEffect(() => {
    onPage.current = true;
    return () => {
      onPage.current = false;
    };
  }, []);

  const quality = qualityLabel(job.quality, qualities);
  const took = durationText(job.build_seconds);
  const built = [
    quality && `Built at ${quality} quality`,
    took && (quality ? `in ${took}` : `Built in ${took}`),
  ]
    .filter(Boolean)
    .join(" ");

  const downloadBlender = async () => {
    setBusy("export");
    setError(null);
    try {
      const { file } = await plan3dApi.exportBlender(jobId);
      // packing can take minutes, so the link is made now: the one the walkthrough was opened with may have run out
      const { files_url: filesUrl } = await plan3dApi.embed(jobId);
      if (!filesUrl)
        throw new Error(
          "The server did not say where the files of this plan are.",
        );
      if (onPage.current) startDownload(jobFileUrl(filesUrl, file));
    } catch (e) {
      setError(`The Blender file could not be prepared. ${plan3dErrorText(e)}`);
    } finally {
      setBusy(null);
    }
  };

  const makeShareLink = async () => {
    setBusy("share");
    setError(null);
    setCopied(false);
    try {
      const { url } = await plan3dApi.share(jobId);
      const absolute = embedUrl(url);
      setShareUrl(absolute);
      try {
        await navigator.clipboard.writeText(absolute);
        setCopied(true);
      } catch {
        // no clipboard access: the link is shown to copy by hand
      }
    } catch (e) {
      setError(`The share link could not be made. ${plan3dErrorText(e)}`);
    } finally {
      setBusy(null);
    }
  };

  const turnOffShareLink = async () => {
    setBusy("share");
    setError(null);
    try {
      await plan3dApi.unshare(jobId);
      setShareUrl(null);
      setCopied(false);
    } catch (e) {
      setError(`The share link could not be turned off. ${plan3dErrorText(e)}`);
    } finally {
      setBusy(null);
    }
  };

  const renderTour = async (quality: "high" | "ultra") => {
    setBusy("tour");
    setError(null);
    try {
      const next = await plan3dApi.tour(jobId, quality);
      onTourStarted?.(next);
    } catch (e) {
      setError(`The video tour could not be started. ${plan3dErrorText(e)}`);
    } finally {
      setBusy(null);
    }
  };

  const renderStills = async (mode: "evening" | "day") => {
    setBusy("stills");
    setError(null);
    try {
      const next = await plan3dApi.stills(jobId, mode);
      onTourStarted?.(next);
    } catch (e) {
      setError(`The stills could not be started. ${plan3dErrorText(e)}`);
    } finally {
      setBusy(null);
    }
  };
  const filesUrl = embed.access?.files_url ?? null;

  const downloadTour = async (file: string) => {
    setError(null);
    try {
      const { files_url: filesUrl } = await plan3dApi.embed(jobId);
      if (!filesUrl)
        throw new Error(
          "The server did not say where the files of this plan are.",
        );
      startDownload(jobFileUrl(filesUrl, file));
    } catch (e) {
      setError(`The video could not be downloaded. ${plan3dErrorText(e)}`);
    }
  };

  const remove = async () => {
    if (
      !window.confirm(
        `Delete "${jobName(job)}" and its 3D house? This cannot be undone.`,
      )
    )
      return;
    setBusy("delete");
    setError(null);
    try {
      await plan3dApi.remove(jobId);
      onDeleted();
    } catch (e) {
      setError(`The plan could not be deleted. ${plan3dErrorText(e)}`);
      setBusy(null);
    }
  };

  const fullScreen = () => {
    // not every browser has it (iPhone Safari), and it may be refused: the walkthrough then stays as it is
    void box.current?.requestFullscreen?.().catch(() => undefined);
  };

  return (
    <section aria-label="Walkthrough" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 break-words font-mono text-xs text-[#a3afbf]">
          {built || "The 3D house is ready."}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={fullScreen}
          disabled={!walkthroughUrl}
          leftIcon={<IconMaximize className="h-3.5 w-3.5" aria-hidden="true" />}
        >
          Full screen
        </Button>
      </div>

      {embed.loading && <StatusNote>Opening the walkthrough…</StatusNote>}
      {embed.error && (
        <ErrorNotice
          message={`The walkthrough could not be opened. ${embed.error}`}
        >
          <Button variant="secondary" size="sm" onClick={embed.reload}>
            Retry
          </Button>
        </ErrorNotice>
      )}
      {embed.access && !walkthroughUrl && (
        <ErrorNotice message="The server did not say where the walkthrough of this plan is." />
      )}
      {walkthroughUrl && (
        // no `sandbox`: the walkthrough locks the pointer to look around and saves screenshots and recordings
        <div
          ref={box}
          className="h-[75vh] min-h-[420px] overflow-hidden rounded-[22px] border border-[#243041] bg-black"
        >
          <iframe
            ref={frame}
            title="3D walkthrough"
            src={embedUrl(walkthroughUrl)}
            allow="fullscreen"
            className="h-full w-full border-0"
          />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={onEdit}
          disabled={busy !== null}
        >
          Edit plan and rebuild
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => void downloadBlender()}
          isLoading={busy === "export"}
          disabled={busy !== null}
          aria-busy={busy === "export"}
          leftIcon={<IconDownload className="h-3.5 w-3.5" aria-hidden="true" />}
        >
          Download Blender file
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => void makeShareLink()}
          isLoading={busy === "share" && !shareUrl}
          disabled={busy !== null}
        >
          {shareUrl ? "New share link" : "Share walkthrough"}
        </Button>
        <LinkButton to="/3d/furniture">Furniture models</LinkButton>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void remove()}
          isLoading={busy === "delete"}
          disabled={busy !== null}
          aria-busy={busy === "delete"}
          leftIcon={<TrashIcon size={14} aria-hidden="true" />}
        >
          Delete
        </Button>
      </div>
      {shareUrl && (
        <div
          className="flex flex-wrap items-center gap-2 text-sm"
          aria-label="Share link"
        >
          <input
            readOnly
            value={shareUrl}
            onFocus={(e) => e.currentTarget.select()}
            aria-label="Share link to the walkthrough"
            className="min-w-0 flex-1 rounded-xl border border-[#243041] bg-[#0e141e] px-2 py-1 text-xs text-white"
          />
          <StatusNote>
            {copied ? "Copied. " : ""}Anyone with this link can walk through the
            house (not edit it). A new link turns the old one off.
          </StatusNote>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void turnOffShareLink()}
            disabled={busy !== null}
          >
            Turn link off
          </Button>
        </div>
      )}
      <div
        className="flex flex-wrap items-center gap-2"
        aria-label="Video tour"
        role="group"
      >
        <span className="font-mono text-xs text-[#a3afbf]">Video tour</span>
        {(["high", "ultra"] as const).map((q) =>
          job.tours[q] ? (
            <Button
              key={q}
              variant="secondary"
              size="sm"
              onClick={() => void downloadTour(job.tours[q].file)}
              leftIcon={
                <IconDownload className="h-3.5 w-3.5" aria-hidden="true" />
              }
            >
              {TOUR_NAMES[q]} video
            </Button>
          ) : (
            <Button
              key={q}
              variant="ghost"
              size="sm"
              onClick={() => void renderTour(q)}
              disabled={busy !== null}
            >
              Render {TOUR_NAMES[q]}
            </Button>
          ),
        )}
      </div>
      <div className="flex flex-col gap-2" aria-label="Stills" role="group">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs text-[#a3afbf]">Photoreal stills</span>
          {(["evening", "day"] as const).map((m) =>
            job.stills[m] ? null : (
              <Button
                key={m}
                variant="ghost"
                size="sm"
                onClick={() => void renderStills(m)}
                disabled={busy !== null}
              >
                Render {STILL_NAMES[m].toLowerCase()} stills
              </Button>
            ),
          )}
        </div>
        {(["evening", "day"] as const).map((m) => {
          const set = job.stills[m];
          if (!set) return null;
          return (
            <div key={m} className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2 text-xs text-[#a3afbf]">
                <span>
                  {STILL_NAMES[m]}: {set.files.length} stills
                  {set.per_still ? `, ${Math.round(set.per_still)} s each` : ""}
                </span>
                {set.tour && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => void downloadTour(set.tour ?? "")}
                    leftIcon={<IconDownload className="h-3.5 w-3.5" aria-hidden="true" />}
                  >
                    Fast tour (1080p)
                  </Button>
                )}
              </div>
              {filesUrl && (
                <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label={`${STILL_NAMES[m]} stills`}>
                  {set.files.map((f) => (
                    <li key={f.name}>
                      <a
                        href={jobFileUrl(filesUrl, f.file)}
                        download
                        className="block overflow-hidden rounded-md border border-white/10"
                        title={`Download ${f.title}`}
                      >
                        <img
                          src={jobFileUrl(filesUrl, f.file)}
                          alt={f.title}
                          loading="lazy"
                          className="aspect-video w-full object-cover"
                        />
                        <span className="block truncate px-2 py-1 text-xs text-[#d6dde6]">{f.title}</span>
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
      {busy === "export" && (
        <StatusNote>
          Packing the Blender file. This can take a few minutes the first time;
          the download starts by itself.
        </StatusNote>
      )}
      {error && <ErrorNotice message={error} />}
    </section>
  );
}
