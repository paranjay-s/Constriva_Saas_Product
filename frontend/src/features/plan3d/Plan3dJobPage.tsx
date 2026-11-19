/**
 * One plan on its way from a PDF to a walkthrough (/3d/:jobId). The page follows the job's
 * status and shows the step it is in:
 *
 * detecting -> review + options -> building -> walkthrough, or a failure of the detection
 * or of the build. A built plan (and one whose build failed) can be reviewed and built again.
 *
 * The review page and the walkthrough are the 3D builder's own pages, in iframes.
 */
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { BackLink, ErrorNotice, LinkButton, PageFrame, PageTitle, StatusNote } from './components/Plan3dParts';
import { Plan3dProgress } from './components/Plan3dProgress';
import { PreviewWalkthrough } from './components/PreviewWalkthrough';
import { Plan3dStepper } from './components/Plan3dStepper';
import { ReviewStep } from './components/ReviewStep';
import { WalkthroughStep } from './components/WalkthroughStep';
import { usePlan3dJob } from './hooks/usePlan3dJob';
import { usePlan3dSystem } from './hooks/usePlan3dSystem';
import { type Plan3dView, canReviewAgain, jobName, jobView, qualityLabel, queueText, timeLeftText } from './plan3dLogic';
import type { Plan3dJob } from './plan3dSchemas';

const EYEBROW = '2D to 3D';

const DETECT_FAILED = 'This drawing could not be read.';
const BUILD_FAILED = 'The 3D house could not be built.';

function JobFlow({ jobId }: { jobId: string }) {
  const navigate = useNavigate();
  const followed = usePlan3dJob(jobId);
  const system = usePlan3dSystem();
  /** The person asked to see the review page again, for a built plan or after a failed build. */
  const [reviewing, setReviewing] = useState(false);
  /** The review page is in the document (shown, or kept out of sight while its build runs). */
  const [reviewOpen, setReviewOpen] = useState(false);

  const { job } = followed;
  const view: Plan3dView | null = job ? (reviewing && canReviewAgain(job) ? 'review' : jobView(job)) : null;

  // The review page stays in the document while the build it started runs. If that build
  // fails, the person gets the plan back as they left it, without the page loading again.
  const keepReview = view === 'review' || (reviewOpen && (view === 'building' || view === 'build_failed'));
  if (keepReview !== reviewOpen) setReviewOpen(keepReview);

  if (followed.notFound) {
    return (
      <PageFrame>
        <BackLink to="/3d">All plans</BackLink>
        <PageTitle eyebrow={EYEBROW} title="This plan was not found">
          It may have been deleted, or it belongs to another account.
        </PageTitle>
        <div>
          <LinkButton to="/3d" variant="primary">
            Back to all plans
          </LinkButton>
        </div>
      </PageFrame>
    );
  }

  if (!job || !view) {
    return (
      <PageFrame>
        <BackLink to="/3d">All plans</BackLink>
        <PageTitle eyebrow={EYEBROW} title="Floor plan" />
        {followed.error ? (
          <ErrorNotice message={followed.error}>
            <Button variant="secondary" size="sm" onClick={followed.retry}>
              Retry
            </Button>
          </ErrorNotice>
        ) : (
          <StatusNote>Loading the plan…</StatusNote>
        )}
      </PageFrame>
    );
  }

  const qualities = system.system?.qualities ?? null;
  const quality = qualityLabel(job.quality, qualities ?? []);

  const started = (next: Plan3dJob) => {
    followed.setJob(next);
    setReviewing(false);
  };

  const buildFacts = [
    quality && `${quality} quality`,
    job.stage === 'queued' ? queueText(job.queue_position) : timeLeftText(job.eta_left),
  ].filter((fact): fact is string => Boolean(fact));

  return (
    <PageFrame wide={view === 'review' || view === 'walkthrough'}>
      <div className="flex flex-col items-start gap-6">
        <BackLink to="/3d">All plans</BackLink>
        <PageTitle eyebrow={EYEBROW} title={jobName(job)} />
        <Plan3dStepper view={view} />
      </div>

      {followed.error && <ErrorNotice message={followed.error} />}
      {followed.stale && !followed.error && <StatusNote>Lost contact with the server. Trying again…</StatusNote>}

      {view === 'detecting' && (
        <Card className="sm:p-8">
          <Plan3dProgress
            title="Reading the drawing"
            label="Detection progress"
            progress={job.stage === 'detecting' ? job.progress : null}
            message={job.message || 'Starting…'}
          />
        </Card>
      )}

      {view === 'detect_failed' && (
        <Card className="flex flex-col gap-6 sm:p-8">
          <h2 className="text-[19px] font-medium text-white">The plan could not be detected</h2>
          <ErrorNotice message={job.message || DETECT_FAILED} />
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-[#243041] pt-4">
            <LinkButton to="/3d" variant="primary">
              Back to all plans
            </LinkButton>
          </div>
        </Card>
      )}

      {keepReview && (
        <ReviewStep
          jobId={jobId}
          hidden={view !== 'review'}
          qualities={qualities}
          qualitiesError={qualities ? null : system.error}
          onRetryQualities={system.reload}
          onBuilt={started}
        >
          {reviewing && (
            <Button variant="ghost" size="sm" onClick={() => setReviewing(false)}>
              {job.stage === 'done' ? 'Back to the walkthrough' : 'Cancel'}
            </Button>
          )}
        </ReviewStep>
      )}

      {view === 'building' && (
        <Card className="sm:p-8">
          <Plan3dProgress
            title={job.stage === 'queued' ? 'Waiting for the 3D builder' : 'Building the 3D house'}
            label="Build progress"
            progress={job.stage === 'queued' ? null : job.progress}
            message={job.message || (job.stage === 'queued' ? 'Waiting…' : 'Building…')}
            facts={buildFacts}
          />
          {job.preview && (
            <div className="mt-6">
              <PreviewWalkthrough jobId={job.job_id} />
            </div>
          )}
        </Card>
      )}

      {view === 'build_failed' && (
        <Card className="flex flex-col gap-6 sm:p-8">
          <h2 className="text-[19px] font-medium text-white">The 3D build failed</h2>
          <ErrorNotice message={job.message || BUILD_FAILED} />
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-[#243041] pt-4">
            <LinkButton to="/3d">Back to all plans</LinkButton>
            <Button variant="primary" size="sm" onClick={() => setReviewing(true)}>
              Review the plan again
            </Button>
          </div>
        </Card>
      )}

      {view === 'walkthrough' && (
        <WalkthroughStep
          job={job}
          qualities={qualities ?? []}
          onEdit={() => setReviewing(true)}
          onDeleted={() => navigate('/3d')}
          onTourStarted={(next) => followed.setJob(next)}
        />
      )}
    </PageFrame>
  );
}

export function Plan3dJobPage() {
  const { jobId = '' } = useParams();
  // what the page remembers (which step was asked for, the open iframes) belongs to one job
  return <JobFlow key={jobId} jobId={jobId} />;
}
