/**
 * The built house: the 3D builder's own walkthrough page in an iframe (walk, top view, map,
 * screenshot, recording), and what can be done with the house from here.
 */
import { useEffect, useRef, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { IconDownload, IconMaximize, TrashIcon } from '../../../components/ui/Icons';
import { useEmbedAccess } from '../hooks/useEmbedAccess';
import { embedUrl, jobFileUrl, plan3dApi, plan3dErrorText, startDownload } from '../plan3dApi';
import { durationText, jobName, qualityLabel } from '../plan3dLogic';
import type { Plan3dJob, Plan3dQuality } from '../plan3dSchemas';
import { ErrorNotice, LinkButton, StatusNote } from './Plan3dParts';

interface WalkthroughStepProps {
  job: Plan3dJob;
  /** The server's names of the build qualities; the built-in names are used without them. */
  qualities: readonly Plan3dQuality[];
  /** Show the review page and the options again, to change the plan and build it once more. */
  onEdit: () => void;
  /** The job was deleted. */
  onDeleted: () => void;
}

export function WalkthroughStep({ job, qualities, onEdit, onDeleted }: WalkthroughStepProps) {
  const jobId = job.job_id;
  const embed = useEmbedAccess(jobId);
  const box = useRef<HTMLDivElement>(null);
  const onPage = useRef(true);
  const [busy, setBusy] = useState<'export' | 'delete' | null>(null);
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
  const built = [quality && `Built at ${quality} quality`, took && (quality ? `in ${took}` : `Built in ${took}`)]
    .filter(Boolean)
    .join(' ');

  const downloadBlender = async () => {
    setBusy('export');
    setError(null);
    try {
      const { file } = await plan3dApi.exportBlender(jobId);
      // packing can take minutes, so the link is made now: the one the walkthrough was opened with may have run out
      const { files_url: filesUrl } = await plan3dApi.embed(jobId);
      if (!filesUrl) throw new Error('The server did not say where the files of this plan are.');
      if (onPage.current) startDownload(jobFileUrl(filesUrl, file));
    } catch (e) {
      setError(`The Blender file could not be prepared. ${plan3dErrorText(e)}`);
    } finally {
      setBusy(null);
    }
  };

  const remove = async () => {
    if (!window.confirm(`Delete "${jobName(job)}" and its 3D house? This cannot be undone.`)) return;
    setBusy('delete');
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
        <div className="min-w-0 break-words font-mono text-xs text-[#A6A6A6]">{built || 'The 3D house is ready.'}</div>
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
        <ErrorNotice message={`The walkthrough could not be opened. ${embed.error}`}>
          <Button variant="secondary" size="sm" onClick={embed.reload}>
            Retry
          </Button>
        </ErrorNotice>
      )}
      {embed.access && !walkthroughUrl && <ErrorNotice message="The server did not say where the walkthrough of this plan is." />}
      {walkthroughUrl && (
        // no `sandbox`: the walkthrough locks the pointer to look around and saves screenshots and recordings
        <div ref={box} className="h-[75vh] min-h-[420px] overflow-hidden rounded-lg border border-[#303030] bg-black">
          <iframe title="3D walkthrough" src={embedUrl(walkthroughUrl)} allow="fullscreen" className="h-full w-full border-0" />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" size="sm" onClick={onEdit} disabled={busy !== null}>
          Edit plan and rebuild
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => void downloadBlender()}
          isLoading={busy === 'export'}
          disabled={busy !== null}
          aria-busy={busy === 'export'}
          leftIcon={<IconDownload className="h-3.5 w-3.5" aria-hidden="true" />}
        >
          Download Blender file
        </Button>
        <LinkButton to="/3d/furniture">Furniture models</LinkButton>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void remove()}
          isLoading={busy === 'delete'}
          disabled={busy !== null}
          aria-busy={busy === 'delete'}
          leftIcon={<TrashIcon size={14} aria-hidden="true" />}
        >
          Delete
        </Button>
      </div>
      {busy === 'export' && (
        <StatusNote>Packing the Blender file. This can take a few minutes the first time; the download starts by itself.</StatusNote>
      )}
      {error && <ErrorNotice message={error} />}
    </section>
  );
}
