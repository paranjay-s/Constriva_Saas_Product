/**
 * Pure logic of the 2D to 3D pages: which step a job is in, the words for its stage, time
 * left, queue position, build quality and the system checks. No React in here, so every
 * rule is easy to test.
 */
import type { Plan3dJob, Plan3dQuality, Plan3dQualityId, Plan3dStage, Plan3dSystem } from './plan3dSchemas';

// -------------------------------------------------------------------- steps

/** What the job page shows for a job. */
export type Plan3dView = 'detecting' | 'detect_failed' | 'review' | 'building' | 'build_failed' | 'walkthrough';

/** The job is being worked on, so its status is worth asking for again. */
export function isActiveStage(stage: Plan3dStage): boolean {
  return stage === 'uploaded' || stage === 'detecting' || stage === 'queued' || stage === 'building';
}

/** A plan was detected in the drawing (so it can be reviewed and built). */
export function hasPlan(job: Pick<Plan3dJob, 'floors'>): boolean {
  return job.floors.length > 0;
}

/** A failure with a plan is a failed build; one without is a drawing that could not be read. */
export function jobView(job: Pick<Plan3dJob, 'stage' | 'floors'>): Plan3dView {
  switch (job.stage) {
    case 'uploaded':
    case 'detecting':
      return 'detecting';
    case 'detected':
      return 'review';
    case 'queued':
    case 'building':
      return 'building';
    case 'done':
      return 'walkthrough';
    case 'failed':
      return hasPlan(job) ? 'build_failed' : 'detect_failed';
  }
}

/** The plan of a built house, or of a failed build, can be reviewed and built again. */
export function canReviewAgain(job: Pick<Plan3dJob, 'stage' | 'floors'>): boolean {
  return hasPlan(job) && (job.stage === 'done' || job.stage === 'failed');
}

export const PLAN3D_STEPS = [
  { id: 'upload', label: 'Upload' },
  { id: 'detect', label: 'Detect' },
  { id: 'review', label: 'Review' },
  { id: 'options', label: 'Options' },
  { id: 'build', label: 'Build' },
  { id: 'walkthrough', label: 'Walkthrough' },
] as const;

export type Plan3dStepState = 'done' | 'active' | 'failed' | 'todo';

/** For each view: the steps in progress (or the one that failed). Earlier steps are done. */
const VIEW_STEPS: Record<Plan3dView, { from: number; to: number; failed?: boolean }> = {
  detecting: { from: 1, to: 1 },
  detect_failed: { from: 1, to: 1, failed: true },
  // the plan is reviewed and the options are chosen on one screen
  review: { from: 2, to: 3 },
  building: { from: 4, to: 4 },
  build_failed: { from: 4, to: 4, failed: true },
  walkthrough: { from: 5, to: 5 },
};

/** State of the six steps of the stepper, in the order of PLAN3D_STEPS. */
export function stepStates(view: Plan3dView): Plan3dStepState[] {
  const { from, to, failed } = VIEW_STEPS[view];
  return PLAN3D_STEPS.map((_, index) => {
    if (index < from) return 'done';
    if (index > to) return 'todo';
    return failed ? 'failed' : 'active';
  });
}

// -------------------------------------------------------------------- words

/** The name to show for a job; the server may have none for it. */
export function jobName(job: Pick<Plan3dJob, 'name'>): string {
  return job.name.trim() || 'Floor plan';
}

/** A job's stage in plain words, for the list of plans. */
export function stageText(job: Pick<Plan3dJob, 'stage' | 'floors'>): string {
  switch (job.stage) {
    case 'uploaded':
    case 'detecting':
      return 'Reading the drawing';
    case 'detected':
      return 'Ready to review';
    case 'queued':
      return 'Waiting to be built';
    case 'building':
      return 'Building the 3D house';
    case 'done':
      return '3D house ready';
    case 'failed':
      return hasPlan(job) ? 'Build failed' : 'Drawing could not be read';
  }
}

function seconds(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
}

/** Time left of a build: "about 2 min left", or "almost done" in the last half minute. */
export function timeLeftText(etaLeft: number | null | undefined): string | null {
  const left = seconds(etaLeft);
  if (left === null) return null;
  if (left < 30) return 'almost done';
  return `about ${Math.round(left / 60)} min left`;
}

function ordinal(n: number): string {
  const lastTwo = n % 100;
  if (lastTwo >= 11 && lastTwo <= 13) return `${n}th`;
  return `${n}${['th', 'st', 'nd', 'rd'][n % 10] ?? 'th'}`;
}

/** Place in the build queue: "Next in the queue", "2nd in the queue". */
export function queueText(position: number | null | undefined): string | null {
  if (typeof position !== 'number' || !Number.isInteger(position) || position < 1) return null;
  return position === 1 ? 'Next in the queue' : `${ordinal(position)} in the queue`;
}

/** How long a build took: "45 s", "3 min 20 s", "1 hr 2 min". */
export function durationText(buildSeconds: number | null | undefined): string | null {
  const total = seconds(buildSeconds);
  if (total === null) return null;
  const whole = Math.round(total);
  if (whole < 60) return `${whole} s`;
  const minutes = Math.floor(whole / 60);
  if (minutes < 60) return whole % 60 ? `${minutes} min ${whole % 60} s` : `${minutes} min`;
  return minutes % 60 ? `${Math.floor(minutes / 60)} hr ${minutes % 60} min` : `${Math.floor(minutes / 60)} hr`;
}

/** A progress figure as a whole percentage between 0 and 100. */
export function percent(progress: number): number {
  return Number.isFinite(progress) ? Math.min(100, Math.max(0, Math.round(progress))) : 0;
}

export function fileSizeText(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ------------------------------------------------------------------ quality

/** Used when the server's own names are not known (yet). */
const QUALITY_NAMES: Record<Plan3dQualityId, string> = { low: 'Low', high: 'High' };

export function findQuality(qualities: readonly Plan3dQuality[], id: Plan3dQualityId | null): Plan3dQuality | null {
  return qualities.find((quality) => quality.id === id) ?? null;
}

/** The name of a quality as the server gives it. */
export function qualityLabel(id: Plan3dQualityId | null | undefined, qualities: readonly Plan3dQuality[] = []): string | null {
  if (!id) return null;
  return findQuality(qualities, id)?.label || QUALITY_NAMES[id];
}

/** Low when it can be built (fast), else whatever can be; null when nothing can. */
export function defaultQuality(qualities: readonly Plan3dQuality[]): Plan3dQualityId | null {
  const available = qualities.filter((quality) => quality.available);
  const preferred = (['low', 'high'] as const).find((id) => available.some((quality) => quality.id === id));
  return preferred ?? available[0]?.id ?? null;
}

// ------------------------------------------------------------------- system

const CHECK_NAMES: Record<string, string> = {
  blender: 'Blender',
  pdf_tools: 'PDF tools',
  viewer: 'viewer library',
  materials: 'materials',
};

function checkFailed(check: unknown): boolean {
  return typeof check === 'object' && check !== null && 'ok' in check && check.ok === false;
}

/** Names of the requirements of the 3D builder that are not in place. */
export function missingChecks(checks: Plan3dSystem['checks']): string[] {
  return Object.entries(checks)
    .filter(([, check]) => checkFailed(check))
    .map(([key]) => CHECK_NAMES[key] ?? key.replace(/_/g, ' '));
}

/** What to tell the person when plans cannot be built right now; null when they can. */
export function systemProblem(system: Plan3dSystem): string | null {
  if (!system.reachable) return system.detail || 'The 3D builder is not running right now. Please try again in a moment.';
  if (system.ready) return null;
  const missing = missingChecks(system.checks);
  if (missing.length === 0) return system.detail || 'The 3D builder is not set up yet.';
  return `The 3D builder is not set up yet. Missing: ${missing.join(', ')}.`;
}
