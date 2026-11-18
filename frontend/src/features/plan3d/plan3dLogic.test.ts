import { afterEach, describe, expect, it, vi } from 'vitest';
import { z } from 'zod';
import { ApiError } from '../../lib/api';
import { embedOrigin, embedUrl, isNotFound, jobFileUrl, plan3dApi, plan3dErrorText } from './plan3dApi';
import { API, EMBED_BASE, HIGH_REASON, JOB_ID, RAW_QUALITIES, RAW_SYSTEM, rawEmbed, rawFurnitureEmbed, rawJob } from './plan3dFixture';
import {
  PLAN3D_STEPS,
  canReviewAgain,
  defaultQuality,
  durationText,
  fileSizeText,
  findQuality,
  hasPlan,
  isActiveStage,
  jobName,
  jobView,
  missingChecks,
  percent,
  qualityLabel,
  queueText,
  stageText,
  stepStates,
  systemProblem,
  timeLeftText,
} from './plan3dLogic';
import {
  type Plan3dStage,
  plan3dEmbedSchema,
  plan3dExportSchema,
  plan3dFrameMessageSchema,
  plan3dJobCreatedSchema,
  plan3dJobListSchema,
  plan3dJobSchema,
  plan3dQualitySchema,
  plan3dSystemSchema,
} from './plan3dSchemas';

const QUALITIES = z.array(plan3dQualitySchema).parse(RAW_QUALITIES);
const job = (overrides: Record<string, unknown> = {}) => plan3dJobSchema.parse(rawJob(overrides));

// ------------------------------------------------------------------ schemas

describe('3D gateway schemas', () => {
  it('parses the system status with its qualities, and changes nothing', () => {
    const system = plan3dSystemSchema.parse(RAW_SYSTEM);
    expect(system).toEqual(RAW_SYSTEM);
    expect(system.qualities.map((quality) => quality.id)).toEqual(['low', 'medium', 'high']);
    expect(system.qualities[2]).toMatchObject({ label: 'High', available: false, reason: HIGH_REASON });
    // the builder cannot be reached: no checks, a sentence instead
    expect(
      plan3dSystemSchema.safeParse({ reachable: false, ready: false, checks: {}, detail: 'Not running.', qualities: [] }).success,
    ).toBe(true);
    expect(plan3dSystemSchema.safeParse({ ...RAW_SYSTEM, qualities: [{ ...RAW_QUALITIES[0], id: 'ultra' }] }).success).toBe(false);
    expect(plan3dSystemSchema.safeParse({ ...RAW_SYSTEM, ready: 'yes' }).success).toBe(false);
  });

  it('parses a job in every stage, with the fields that are null until they are known', () => {
    expect(job()).toEqual(rawJob());
    const stages = ['uploaded', 'detecting', 'detected', 'queued', 'building', 'done', 'failed'];
    for (const stage of stages) expect(plan3dJobSchema.safeParse(rawJob({ stage })).success, stage).toBe(true);
    const built = job({ stage: 'done', quality: 'medium', build_seconds: 200, project_id: 'p-1', source: 'sample' });
    expect(built).toMatchObject({ quality: 'medium', build_seconds: 200, project_id: 'p-1', source: 'sample' });
    const waiting = job({ stage: 'queued', queue_position: 2, eta_left: null });
    expect(waiting.queue_position).toBe(2);
    // a field the server adds later is kept, not refused
    expect(job({ added_later: true })).toMatchObject({ added_later: true });
  });

  it('refuses a job that breaks the contract', () => {
    expect(plan3dJobSchema.safeParse(rawJob({ stage: 'rendering' })).success).toBe(false);
    expect(plan3dJobSchema.safeParse(rawJob({ quality: 'draft' })).success).toBe(false);
    expect(plan3dJobSchema.safeParse(rawJob({ source: 'import' })).success).toBe(false);
    expect(plan3dJobSchema.safeParse(rawJob({ progress: '40' })).success).toBe(false);
    expect(plan3dJobSchema.safeParse(rawJob({ floors: null })).success).toBe(false);
    const { job_id: _dropped, ...withoutId } = rawJob();
    expect(plan3dJobSchema.safeParse(withoutId).success).toBe(false);
  });

  it('parses the job list, the created job and the export answer', () => {
    expect(plan3dJobListSchema.parse([rawJob(), rawJob({ job_id: 'ffffffffffff', stage: 'done' })])).toHaveLength(2);
    expect(plan3dJobListSchema.parse([])).toEqual([]);
    expect(plan3dJobListSchema.safeParse([rawJob(), { job_id: 'x' }]).success).toBe(false);
    expect(plan3dJobCreatedSchema.parse({ job_id: JOB_ID })).toEqual({ job_id: JOB_ID });
    expect(plan3dJobCreatedSchema.safeParse({ id: JOB_ID }).success).toBe(false);
    expect(plan3dExportSchema.parse({ file: 'house_blender.zip' })).toEqual({ file: 'house_blender.zip' });
    expect(plan3dExportSchema.safeParse({ url: '/jobs/x/house_blender.zip' }).success).toBe(false);
  });

  it('accepts embed URLs only as paths of the gateway', () => {
    expect(plan3dEmbedSchema.parse(rawEmbed())).toEqual(rawEmbed());
    const furniture = plan3dEmbedSchema.parse(rawFurnitureEmbed());
    expect(furniture).toMatchObject({ review_url: null, walkthrough_url: null, files_url: null });
    expect(furniture.furniture_url).toBe(`${EMBED_BASE}/web/furniture.html?embed`);

    // prefixed with the API's address these would point somewhere else
    for (const elsewhere of ['https://evil.example/edit.html', '@evil.example/edit.html', '//evil.example/x', '/api/v1/other']) {
      expect(plan3dEmbedSchema.safeParse({ ...rawEmbed(), review_url: elsewhere }).success, elsewhere).toBe(false);
      expect(plan3dEmbedSchema.safeParse({ ...rawEmbed(), furniture_url: elsewhere }).success, elsewhere).toBe(false);
    }
    expect(plan3dEmbedSchema.safeParse({ ...rawEmbed(), furniture_url: null }).success).toBe(false);
    expect(plan3dEmbedSchema.safeParse({ ...rawEmbed(), expires_in: '3600' }).success).toBe(false);
  });

  it('reads the three messages of the review page', () => {
    const from = { source: 'planto3d', job: JOB_ID };
    expect(plan3dFrameMessageSchema.parse({ ...from, type: 'ready', floors: 2 })).toMatchObject({ type: 'ready', floors: 2 });
    expect(plan3dFrameMessageSchema.parse({ ...from, type: 'failed', message: 'No plan found.' })).toMatchObject({
      type: 'failed',
      message: 'No plan found.',
    });
    expect(plan3dFrameMessageSchema.parse({ ...from, type: 'saved', ok: true, error: null })).toMatchObject({ ok: true });
    expect(plan3dFrameMessageSchema.parse({ ...from, type: 'saved', ok: false, error: 'invalid plan' })).toMatchObject({
      ok: false,
      error: 'invalid plan',
    });
    // a refused save whose answer had no error text still counts as "not saved"
    expect(plan3dFrameMessageSchema.safeParse({ ...from, type: 'saved', ok: false }).success).toBe(true);
    expect(plan3dFrameMessageSchema.safeParse({ ...from, type: 'saved', ok: false, error: undefined }).success).toBe(true);
  });

  it('refuses anything else posted to the window', () => {
    const from = { source: 'planto3d', job: JOB_ID };
    expect(plan3dFrameMessageSchema.safeParse({ ...from, source: 'planto3d-host', type: 'ready', floors: 1 }).success).toBe(false);
    expect(plan3dFrameMessageSchema.safeParse({ source: 'planto3d', type: 'ready', floors: 1 }).success).toBe(false);
    expect(plan3dFrameMessageSchema.safeParse({ ...from, type: 'built' }).success).toBe(false);
    expect(plan3dFrameMessageSchema.safeParse({ ...from, type: 'saved', ok: 'yes' }).success).toBe(false);
    expect(plan3dFrameMessageSchema.safeParse({ ...from, type: 'saved' }).success).toBe(false);
    for (const junk of [null, undefined, 'saved', 42, [], {}]) {
      expect(plan3dFrameMessageSchema.safeParse(junk).success).toBe(false);
    }
  });
});

// -------------------------------------------------------------------- logic

describe('which step a job is in', () => {
  it('maps every stage to what the page shows', () => {
    expect(jobView(job({ stage: 'uploaded', floors: [] }))).toBe('detecting');
    expect(jobView(job({ stage: 'detecting', floors: [] }))).toBe('detecting');
    expect(jobView(job({ stage: 'detected' }))).toBe('review');
    expect(jobView(job({ stage: 'queued' }))).toBe('building');
    expect(jobView(job({ stage: 'building' }))).toBe('building');
    expect(jobView(job({ stage: 'done' }))).toBe('walkthrough');
  });

  it('tells a drawing that could not be read from a build that failed', () => {
    expect(jobView(job({ stage: 'failed', floors: [] }))).toBe('detect_failed');
    expect(jobView(job({ stage: 'failed', floors: ['Ground floor'] }))).toBe('build_failed');
    expect(hasPlan(job({ floors: [] }))).toBe(false);
    expect(hasPlan(job())).toBe(true);
  });

  it('follows a job only while it is being worked on', () => {
    const active: Plan3dStage[] = ['uploaded', 'detecting', 'queued', 'building'];
    const settled: Plan3dStage[] = ['detected', 'done', 'failed'];
    for (const stage of active) expect(isActiveStage(stage), stage).toBe(true);
    for (const stage of settled) expect(isActiveStage(stage), stage).toBe(false);
  });

  it('lets a built plan, or one whose build failed, be reviewed again', () => {
    expect(canReviewAgain(job({ stage: 'done' }))).toBe(true);
    expect(canReviewAgain(job({ stage: 'failed' }))).toBe(true);
    expect(canReviewAgain(job({ stage: 'failed', floors: [] }))).toBe(false);
    expect(canReviewAgain(job({ stage: 'building' }))).toBe(false);
    expect(canReviewAgain(job({ stage: 'detected' }))).toBe(false); // it is on the review step already
  });

  it('marks the steps of the stepper', () => {
    expect(PLAN3D_STEPS.map((step) => step.label)).toEqual(['Upload', 'Detect', 'Review', 'Options', 'Build', 'Walkthrough']);
    expect(stepStates('detecting')).toEqual(['done', 'active', 'todo', 'todo', 'todo', 'todo']);
    expect(stepStates('detect_failed')).toEqual(['done', 'failed', 'todo', 'todo', 'todo', 'todo']);
    // the plan is reviewed and the options chosen on one screen
    expect(stepStates('review')).toEqual(['done', 'done', 'active', 'active', 'todo', 'todo']);
    expect(stepStates('building')).toEqual(['done', 'done', 'done', 'done', 'active', 'todo']);
    expect(stepStates('build_failed')).toEqual(['done', 'done', 'done', 'done', 'failed', 'todo']);
    expect(stepStates('walkthrough')).toEqual(['done', 'done', 'done', 'done', 'done', 'active']);
  });
});

describe('words for a job', () => {
  it('says the stage in plain words', () => {
    expect(stageText(job({ stage: 'uploaded', floors: [] }))).toBe('Reading the drawing');
    expect(stageText(job({ stage: 'detecting', floors: [] }))).toBe('Reading the drawing');
    expect(stageText(job({ stage: 'detected' }))).toBe('Ready to review');
    expect(stageText(job({ stage: 'queued' }))).toBe('Waiting to be built');
    expect(stageText(job({ stage: 'building' }))).toBe('Building the 3D house');
    expect(stageText(job({ stage: 'done' }))).toBe('3D house ready');
    expect(stageText(job({ stage: 'failed' }))).toBe('Build failed');
    expect(stageText(job({ stage: 'failed', floors: [] }))).toBe('Drawing could not be read');
  });

  it('names a job, also one the server has no name for', () => {
    expect(jobName(job())).toBe('green-villa.pdf');
    expect(jobName(job({ name: '  ' }))).toBe('Floor plan');
  });

  it('gives the time left of a build', () => {
    expect(timeLeftText(120)).toBe('about 2 min left');
    expect(timeLeftText(600)).toBe('about 10 min left');
    expect(timeLeftText(89)).toBe('about 1 min left');
    expect(timeLeftText(90)).toBe('about 2 min left');
    expect(timeLeftText(30)).toBe('about 1 min left');
    expect(timeLeftText(29)).toBe('almost done');
    expect(timeLeftText(0)).toBe('almost done');
    expect(timeLeftText(null)).toBeNull();
    expect(timeLeftText(undefined)).toBeNull();
    expect(timeLeftText(-5)).toBeNull();
    expect(timeLeftText(Number.NaN)).toBeNull();
  });

  it('gives the place in the queue', () => {
    expect(queueText(1)).toBe('Next in the queue');
    expect(queueText(2)).toBe('2nd in the queue');
    expect(queueText(3)).toBe('3rd in the queue');
    expect(queueText(4)).toBe('4th in the queue');
    expect(queueText(11)).toBe('11th in the queue');
    expect(queueText(12)).toBe('12th in the queue');
    expect(queueText(13)).toBe('13th in the queue');
    expect(queueText(21)).toBe('21st in the queue');
    expect(queueText(22)).toBe('22nd in the queue');
    expect(queueText(101)).toBe('101st in the queue');
    expect(queueText(111)).toBe('111th in the queue');
    expect(queueText(null)).toBeNull();
    expect(queueText(0)).toBeNull();
    expect(queueText(1.5)).toBeNull();
  });

  it('says how long a build took', () => {
    expect(durationText(45)).toBe('45 s');
    expect(durationText(200)).toBe('3 min 20 s');
    expect(durationText(180)).toBe('3 min');
    expect(durationText(3720)).toBe('1 hr 2 min');
    expect(durationText(7200)).toBe('2 hr');
    expect(durationText(0)).toBe('0 s');
    expect(durationText(null)).toBeNull();
    expect(durationText(-1)).toBeNull();
  });

  it('keeps a progress figure between 0 and 100', () => {
    expect(percent(41.6)).toBe(42);
    expect(percent(-3)).toBe(0);
    expect(percent(250)).toBe(100);
    expect(percent(Number.NaN)).toBe(0);
  });

  it('formats a file size', () => {
    expect(fileSizeText(2048)).toBe('2.0 KB');
    expect(fileSizeText(5 * 1024 * 1024)).toBe('5.0 MB');
  });
});

describe('build quality', () => {
  const only = (...available: string[]) => QUALITIES.map((quality) => ({ ...quality, available: available.includes(quality.id) }));

  it('starts on Medium, or on Low when Medium cannot be built', () => {
    expect(defaultQuality(QUALITIES)).toBe('medium');
    expect(defaultQuality(only('low', 'high'))).toBe('low');
    expect(defaultQuality(only('high'))).toBe('high');
    expect(defaultQuality(only())).toBeNull();
    expect(defaultQuality([])).toBeNull();
  });

  it("uses the server's names, and its own when the server's are not known", () => {
    expect(qualityLabel('medium', QUALITIES)).toBe('Medium');
    expect(qualityLabel('low', [{ ...QUALITIES[0], label: 'Draft' }])).toBe('Draft');
    expect(qualityLabel('high')).toBe('High');
    expect(qualityLabel('low', [])).toBe('Low');
    expect(qualityLabel(null, QUALITIES)).toBeNull();
    expect(findQuality(QUALITIES, 'high')?.reason).toBe(HIGH_REASON);
    expect(findQuality(QUALITIES, null)).toBeNull();
  });
});

describe('system status', () => {
  const system = (overrides: Record<string, unknown>) => plan3dSystemSchema.parse({ ...RAW_SYSTEM, ...overrides });

  it('names what is missing', () => {
    expect(missingChecks(RAW_SYSTEM.checks)).toEqual([]);
    expect(
      missingChecks({
        blender: { ok: false, version: '' },
        pdf_tools: { ok: false },
        viewer: { ok: false },
        materials: { ok: false, running: true, done: 3, total: 40, failed: [] },
      }),
    ).toEqual(['Blender', 'PDF tools', 'viewer library', 'materials']);
    expect(missingChecks({ blender: { ok: true }, pdf_tools: { ok: false } })).toEqual(['PDF tools']);
    // a requirement this page has never heard of is named as the server names it
    expect(missingChecks({ gpu_driver: { ok: false } })).toEqual(['gpu driver']);
    // only a check that says it failed counts
    expect(missingChecks({ blender: null, viewer: 'no', materials: {}, pdf_tools: { ok: 0 } })).toEqual([]);
  });

  it('says nothing when plans can be built', () => {
    expect(systemProblem(system({}))).toBeNull();
  });

  it('says that the builder is not running', () => {
    const detail = 'The 3D builder is not running right now. Please try again in a moment.';
    expect(systemProblem(system({ reachable: false, ready: false, checks: {}, detail }))).toBe(detail);
    expect(systemProblem(system({ reachable: false, ready: false, checks: {}, detail: '' }))).toMatch(/not running right now/);
  });

  it('says what the builder still needs', () => {
    const checks = { ...RAW_SYSTEM.checks, blender: { ok: false, version: '' }, materials: { ok: false } };
    expect(systemProblem(system({ ready: false, checks }))).toBe('The 3D builder is not set up yet. Missing: Blender, materials.');
    expect(systemProblem(system({ ready: false }))).toBe('The 3D builder is not set up yet.');
  });
});

// ---------------------------------------------------------------------- API

describe('3D API helpers', () => {
  it('prefixes embed paths with the address of the API', () => {
    expect(embedUrl(`${EMBED_BASE}/web/view.html?job=${JOB_ID}&embed`)).toBe(`${API}${EMBED_BASE}/web/view.html?job=${JOB_ID}&embed`);
    expect(embedOrigin()).toBe(API);
    expect(jobFileUrl(`${EMBED_BASE}/jobs/${JOB_ID}`, 'house_blender.zip')).toBe(`${API}${EMBED_BASE}/jobs/${JOB_ID}/house_blender.zip`);
    // a file name cannot climb out of the job's folder
    expect(jobFileUrl(`${EMBED_BASE}/jobs/${JOB_ID}`, '../other/secret.zip')).toBe(
      `${API}${EMBED_BASE}/jobs/${JOB_ID}/..%2Fother%2Fsecret.zip`,
    );
  });

  it('turns whatever was thrown into a sentence', () => {
    expect(plan3dErrorText(new ApiError(503, 'The 3D builder is not running right now.'))).toBe('The 3D builder is not running right now.');
    // a 422 carries a list of issues instead of a sentence
    const unreadable = new ApiError(422, '');
    Object.assign(unreadable, { detail: [{ msg: 'field required', loc: ['body', 'file'] }] });
    expect(plan3dErrorText(unreadable)).toBe('The request could not be completed (422).');
    expect(plan3dErrorText(plan3dJobSchema.safeParse({}).error)).toMatch(/could not read/);
    expect(plan3dErrorText(new TypeError('Failed to fetch'))).toMatch(/could not reach the server/i);
    expect(plan3dErrorText(new Error('The plan could not be saved.'))).toBe('The plan could not be saved.');
    expect(plan3dErrorText('nope')).toBe('Something went wrong.');
    expect(isNotFound(new ApiError(404, '3D job not found.'))).toBe(true);
    expect(isNotFound(new ApiError(409, 'busy'))).toBe(false);
    expect(isNotFound(new Error('404'))).toBe(false);
  });
});

describe('Open in 3D from the floor plan generator', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('asks the gateway for a job made from the stored plan', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ job_id: JOB_ID }), { status: 201, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    expect(await plan3dApi.fromFloorplan('5b1f0e7a-2c44-4d0b-9a61-7e3c2d9f4a10')).toEqual({ job_id: JOB_ID });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`${API}/api/v1/3d/jobs/from-floorplan`);
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toEqual({ plan_id: '5b1f0e7a-2c44-4d0b-9a61-7e3c2d9f4a10' });
  });

  it('accepts a job made from a floor plan, with the reader that made its plan', () => {
    const job = plan3dJobSchema.parse({ ...rawJob(), source: 'floorplan', reader: 'stored', notice: 'From your floor plan' });
    expect(job.source).toBe('floorplan');
    expect(job.reader).toBe('stored');
  });
});
