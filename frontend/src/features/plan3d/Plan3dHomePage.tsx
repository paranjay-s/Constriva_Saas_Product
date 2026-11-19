/**
 * 2D to 3D (/3d): upload a floor-plan PDF (or try the sample plan) to start a 3D job, and
 * the list of the plans started before. Each plan continues on its own page (/3d/:jobId).
 *
 * With a saved project chosen in the app, new plans are stored in that project and the
 * list shows that project's plans.
 */
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { ArrowRightIcon, IconRefresh } from '../../components/ui/Icons';
import { useProject } from '../../context/ProjectContext';
import { planFileProblem, useUploadLimits } from '../files';
import { isSavedProject } from '../floorplan';
import { Plan3dJobList } from './components/Plan3dJobList';
import { BackLink, ErrorNotice, LinkButton, PageFrame, PageTitle, StatusNote } from './components/Plan3dParts';
import { Plan3dUpload } from './components/Plan3dUpload';
import { usePlan3dJobs } from './hooks/usePlan3dJobs';
import { Plan3dNotices } from './components/Plan3dNotices';
import { usePlan3dSystem } from './hooks/usePlan3dSystem';
import { plan3dApi, plan3dErrorText } from './plan3dApi';
import { jobName, systemProblem } from './plan3dLogic';
import type { Plan3dJob } from './plan3dSchemas';

export function Plan3dHomePage() {
  const navigate = useNavigate();
  const { activeProject, projects, isLoadingProjects } = useProject();
  // only a project that exists in the account is sent to the server (not the local placeholder)
  const project = isSavedProject(activeProject, projects) ? activeProject : null;
  const limits = useUploadLimits();
  const system = usePlan3dSystem();

  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [starting, setStarting] = useState<'upload' | 'sample' | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);

  const [everyProject, setEveryProject] = useState(false);
  const list = usePlan3dJobs(project && !everyProject ? project.id : null, !isLoadingProjects);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // leaving the page cancels an upload that is still in flight
  useEffect(() => () => request.current?.abort(), []);

  const pick = (picked: File) => {
    const problem = planFileProblem(picked, limits);
    setFileError(problem);
    setStartError(null);
    if (!problem) setFile(picked);
  };

  // Until the account's projects are known it is not known which project a new plan belongs to.
  const canStart = starting === null && !isLoadingProjects;

  /** Start a job from the picked PDF or from the sample plan, then go to its page. */
  const start = async (from: 'upload' | 'sample') => {
    if (!canStart || (from === 'upload' && !file)) return;
    const controller = new AbortController();
    request.current = controller;
    setStarting(from);
    setStartError(null);
    try {
      const created =
        from === 'upload' && file
          ? await plan3dApi.upload(file, project?.id, controller.signal)
          : await plan3dApi.sample(project?.id, controller.signal);
      if (!controller.signal.aborted) navigate(`/3d/${encodeURIComponent(created.job_id)}`);
    } catch (e) {
      if (controller.signal.aborted) return;
      setStartError(plan3dErrorText(e));
      setStarting(null);
    }
  };

  const remove = async (job: Plan3dJob) => {
    if (!window.confirm(`Delete "${jobName(job)}" and its 3D house? This cannot be undone.`)) return;
    setDeletingId(job.job_id);
    setDeleteError(null);
    try {
      await plan3dApi.remove(job.job_id);
      list.drop(job.job_id);
    } catch (e) {
      setDeleteError(`"${jobName(job)}" could not be deleted. ${plan3dErrorText(e)}`);
    } finally {
      setDeletingId(null);
    }
  };

  const builderProblem = system.system ? systemProblem(system.system) : null;

  return (
    <PageFrame>
      <div className="flex flex-col items-start gap-6">
        <BackLink to="/home">Back to Home</BackLink>
        <PageTitle eyebrow="Pillar 01 // Spatial BIM" title="2D Plan to 3D">
          Upload a floor plan PDF, check the plan that was detected in it, and walk through the house in 3D.
        </PageTitle>
      </div>

      <Plan3dNotices />

      {builderProblem && (
        <ErrorNotice message={builderProblem}>
          <Button variant="secondary" size="sm" onClick={system.reload} isLoading={system.loading}>
            Check again
          </Button>
        </ErrorNotice>
      )}

      <Card className="flex flex-col gap-6 sm:p-8">
        {fileError && <ErrorNotice message={fileError} />}
        {startError && <ErrorNotice message={startError} />}
        <Plan3dUpload
          file={file}
          limits={limits}
          disabled={starting !== null}
          onPick={pick}
          onClear={() => {
            setFile(null);
            setFileError(null);
            setStartError(null);
          }}
        />
        {project && (
          <div className="break-words text-xs text-[#a3afbf]">
            New plans are saved in the project <span className="font-semibold text-white">{project.name}</span>.
          </div>
        )}
        {starting && <StatusNote>{starting === 'upload' ? 'Uploading the PDF…' : 'Starting the sample plan…'}</StatusNote>}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#243041] pt-4">
          <Button
            variant="secondary"
            onClick={() => void start('sample')}
            isLoading={starting === 'sample'}
            disabled={!canStart}
            aria-busy={starting === 'sample'}
          >
            Try the sample plan
          </Button>
          <Button
            variant="primary"
            size="lg"
            onClick={() => void start('upload')}
            isLoading={starting === 'upload'}
            disabled={!file || !canStart}
            aria-busy={starting === 'upload'}
            rightIcon={<ArrowRightIcon size={16} aria-hidden="true" />}
          >
            Upload plan
          </Button>
        </div>
      </Card>

      <section aria-label="Your plans" className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-1">
            <h2 className="text-[19px] font-medium text-white">Your plans</h2>
            {project && (
              <div className="break-words text-xs text-[#a3afbf]">
                {everyProject ? 'From all your projects' : `In the project ${project.name}`}
              </div>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {project && (
              <Button variant="ghost" size="sm" onClick={() => setEveryProject((all) => !all)}>
                {everyProject ? 'Show this project only' : 'Show all plans'}
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={list.reload}
              disabled={list.loading}
              leftIcon={<IconRefresh className="h-3.5 w-3.5" aria-hidden="true" />}
            >
              Refresh
            </Button>
            <LinkButton to="/3d/furniture">Furniture models</LinkButton>
          </div>
        </div>

        {deleteError && <ErrorNotice message={deleteError} />}
        {list.loading && <StatusNote>Loading your plans…</StatusNote>}
        {list.error && (
          <ErrorNotice message={`Your plans could not be loaded. ${list.error}`}>
            <Button variant="secondary" size="sm" onClick={list.reload}>
              Retry
            </Button>
          </ErrorNotice>
        )}
        {list.jobs &&
          (list.jobs.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#243041] p-6 text-center text-sm text-[#8b97a8]">
              No plans yet. Upload a floor plan PDF, or try the sample plan.
            </div>
          ) : (
            <Plan3dJobList
              jobs={list.jobs}
              qualities={system.system?.qualities ?? []}
              deletingId={deletingId}
              onDelete={(job) => void remove(job)}
            />
          ))}
      </section>
    </PageFrame>
  );
}
