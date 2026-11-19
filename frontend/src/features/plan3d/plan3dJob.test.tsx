import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { TOKEN_STORAGE_KEY } from '../../lib/api';
import { SAVE_TIMEOUT_MS } from './components/ReviewStep';
import { PLAN3D_POLL_MS } from './hooks/usePlan3dJob';
import { Plan3dJobPage } from './Plan3dJobPage';
import {
  API,
  BASE,
  EMBED_BASE,
  HIGH_REASON,
  JOB_ID,
  type MockRoutes,
  RAW_SYSTEM,
  TOKEN,
  authorizationOf,
  callsTo,
  json,
  mockFetch,
  noContent,
  rawEmbed,
  rawJob,
} from './plan3dFixture';

const JOB = `${BASE}/jobs/${JOB_ID}`;
const REVIEW_SRC = `${API}${EMBED_BASE}/web/edit.html?job=${JOB_ID}&embed`;
const WALK_SRC = `${API}${EMBED_BASE}/web/view.html?job=${JOB_ID}&embed`;
const REVIEW = 'Review the detected plan';
const WALK = '3D walkthrough';

const QUEUED = rawJob({ stage: 'queued', progress: 0, message: 'Waiting for the 3D builder (1 ahead)', quality: 'medium', queue_position: 2 });
const DONE = rawJob({ stage: 'done', progress: 100, message: 'Ready', quality: 'medium', build_seconds: 200 });
const BUILD_FAILED = rawJob({ stage: 'failed', progress: 30, message: '3D build failed - see build.log' });

/** Answers one after the other, then keeps giving the last one. */
function inTurn(...answers: (() => Response)[]) {
  let next = 0;
  return () => answers[Math.min(next++, answers.length - 1)]();
}

const statuses = (...jobs: unknown[]) => inTurn(...jobs.map((job) => () => json(job)));

/** The API as it answers for a plan that was just detected; a test replaces the answers it is about. */
function mockApi(routes: MockRoutes = {}) {
  return mockFetch({
    [`GET ${BASE}/system`]: () => json(RAW_SYSTEM),
    [`GET ${JOB}`]: () => json(rawJob()),
    [`POST ${JOB}/embed`]: () => json(rawEmbed()),
    ...routes,
  });
}

function renderJob() {
  return render(
    <MemoryRouter initialEntries={[`/3d/${JOB_ID}`]}>
      <Routes>
        <Route path="/3d" element={<div>all plans page</div>} />
        <Route path="/3d/furniture" element={<div>furniture page</div>} />
        <Route path="/3d/:jobId" element={<Plan3dJobPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** The steps of the stepper as "Label (state)", and the one marked as current. */
function steps() {
  const items = within(screen.getByRole('list', { name: 'Steps' })).getAllByRole('listitem');
  const text = (item: HTMLElement) => (item.textContent ?? '').replace(/^\d+/, '');
  return { all: items.map(text), current: items.filter((item) => item.getAttribute('aria-current') === 'step').map(text) };
}

function frame(title: string): HTMLIFrameElement {
  const found = screen.getByTitle(title);
  if (!(found instanceof HTMLIFrameElement)) throw new Error(`${title} is not an iframe`);
  return found;
}

function pageOf(element: HTMLIFrameElement): Window {
  if (!element.contentWindow) throw new Error('the iframe has no window');
  return element.contentWindow;
}

/** A window that is not the review page's. */
function anotherWindow(): Window {
  const other = document.createElement('iframe');
  document.body.appendChild(other);
  return pageOf(other);
}

/** Deliver a message to the app's window, by default as the review page of this job would send it. */
function post(data: unknown, from: { origin?: string; source?: Window } = {}) {
  fireEvent(
    window,
    new MessageEvent('message', { data, origin: from.origin ?? API, source: from.source ?? pageOf(frame(REVIEW)) }),
  );
}

const READY = { source: 'planto3d', job: JOB_ID, type: 'ready', floors: 2 };
const SAVED = { source: 'planto3d', job: JOB_ID, type: 'saved', ok: true, error: null };

const options = () => within(screen.getByRole('region', { name: 'Build options' }));
const buildButton = () => options().getByRole('button', { name: 'Build 3D' });
const isDisabled = (element: HTMLElement) => element.hasAttribute('disabled');

/** The review step with the plan loaded: the review page said "ready" and the qualities have arrived. */
async function openReview() {
  await screen.findByTitle(REVIEW);
  await options().findByRole('radio', { name: 'Medium' });
  post(READY);
  expect(isDisabled(buildButton())).toBe(false);
  return vi.spyOn(pageOf(frame(REVIEW)), 'postMessage').mockImplementation(() => {});
}

// Only the timers of the page are faked; requests are answered as usual.
const fakeClock = () => vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] });
const advance = (ms: number) =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
/** Let the requests in flight be answered and the page render, without moving the clock. */
const settle = async () => {
  for (let turn = 0; turn < 5; turn += 1) await advance(0);
};

describe('3D job page', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(TOKEN_STORAGE_KEY, 'test-jwt-token');
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // --------------------------------------------------------------- detecting

  describe('while the drawing is read', () => {
    it('shows the detection progress and asks again every 1.5 s until the plan is detected', async () => {
      fakeClock();
      const fetchMock = mockApi({
        [`GET ${JOB}`]: statuses(
          rawJob({ stage: 'uploaded', progress: 0, message: 'Uploaded', floors: [] }),
          rawJob({ stage: 'detecting', progress: 40, message: 'Reading the drawing', floors: [] }),
          rawJob(),
        ),
      });
      const asked = () => callsTo(fetchMock, 'GET', JOB).length;
      renderJob();
      await settle();

      expect(PLAN3D_POLL_MS).toBe(1500);
      expect(screen.getByRole('heading', { level: 1, name: 'green-villa.pdf' })).toBeDefined();
      const bar = () => screen.getByRole('progressbar', { name: 'Detection progress' });
      expect(bar().hasAttribute('aria-valuenow')).toBe(false); // nothing to count yet
      expect(screen.getByRole('status').textContent).toBe('Uploaded');
      expect(steps().all).toEqual([
        'Upload (done)',
        'Detect (in progress)',
        'Review (not started)',
        'Options (not started)',
        'Build (not started)',
        'Walkthrough (not started)',
      ]);
      expect(steps().current).toEqual(['Detect (in progress)']);
      expect(asked()).toBe(1);

      await advance(PLAN3D_POLL_MS - 1);
      expect(asked()).toBe(1);
      await advance(1);
      expect(asked()).toBe(2);
      expect(bar().getAttribute('aria-valuenow')).toBe('40');
      expect(screen.getByText('40%')).toBeDefined();
      expect(screen.getByRole('status').textContent).toBe('Reading the drawing');
      expect(screen.queryByTitle(REVIEW)).toBeNull();
      expect(callsTo(fetchMock, 'POST', `${JOB}/embed`)).toHaveLength(0); // no iframe yet, so no link is asked for

      await advance(PLAN3D_POLL_MS);
      await settle();
      expect(asked()).toBe(3);
      expect(frame(REVIEW).getAttribute('src')).toBe(REVIEW_SRC);
      expect(screen.queryByRole('progressbar')).toBeNull();

      // the plan is detected: nothing is asked any more
      await advance(PLAN3D_POLL_MS * 6);
      expect(asked()).toBe(3);
      expect(authorizationOf(callsTo(fetchMock, 'GET', JOB)[0])).toBe('Bearer test-jwt-token');
    });

    it('stops asking when the page is left', async () => {
      fakeClock();
      const fetchMock = mockApi({
        [`GET ${JOB}`]: () => json(rawJob({ stage: 'detecting', progress: 10, message: 'Reading the drawing', floors: [] })),
      });
      const { unmount } = renderJob();
      await settle();
      await advance(PLAN3D_POLL_MS);
      expect(callsTo(fetchMock, 'GET', JOB)).toHaveLength(2);

      unmount();
      await advance(PLAN3D_POLL_MS * 6);
      expect(callsTo(fetchMock, 'GET', JOB)).toHaveLength(2);
    });

    it('keeps following when a request fails in between', async () => {
      fakeClock();
      const detecting = (progress: number) => () => json(rawJob({ stage: 'detecting', progress, message: 'Reading the drawing', floors: [] }));
      mockApi({
        [`GET ${JOB}`]: inTurn(detecting(10), () => json({ detail: 'The 3D builder is not running right now.' }, 503), detecting(70)),
      });
      renderJob();
      await settle();
      const bar = () => screen.getByRole('progressbar', { name: 'Detection progress' });
      expect(bar().getAttribute('aria-valuenow')).toBe('10');

      await advance(PLAN3D_POLL_MS);
      await settle();
      expect(screen.getByText('Lost contact with the server. Trying again…')).toBeDefined();
      expect(bar().getAttribute('aria-valuenow')).toBe('10'); // the last status stays on screen
      expect(screen.queryByRole('alert')).toBeNull();

      await advance(PLAN3D_POLL_MS);
      await settle();
      expect(screen.queryByText(/lost contact/i)).toBeNull();
      expect(bar().getAttribute('aria-valuenow')).toBe('70');
    });
  });

  describe('when the drawing could not be read', () => {
    it("shows the job's message and a link back to all plans", async () => {
      const message = 'This drawing could not be read. Is it a floor plan exported from a CAD tool?';
      const fetchMock = mockApi({ [`GET ${JOB}`]: () => json(rawJob({ stage: 'failed', progress: 0, message, floors: [] })) });
      renderJob();
      expect((await screen.findByRole('alert')).textContent).toBe(message);
      expect(screen.getByRole('heading', { name: 'The plan could not be detected' })).toBeDefined();
      expect(screen.getByRole('link', { name: 'Back to all plans' }).getAttribute('href')).toBe('/3d');
      expect(steps().all.slice(0, 3)).toEqual(['Upload (done)', 'Detect (failed)', 'Review (not started)']);
      expect(steps().current).toEqual(['Detect (failed)']);
      // there is no plan to review or build
      expect(screen.queryByRole('button', { name: 'Review the plan again' })).toBeNull();
      expect(screen.queryByTitle(REVIEW)).toBeNull();
      expect(callsTo(fetchMock, 'POST', `${JOB}/embed`)).toHaveLength(0);
    });
  });

  // ------------------------------------------------------------------ review

  describe('review and options', () => {
    it('shows the review page in an iframe, next to the options', async () => {
      const fetchMock = mockApi();
      renderJob();
      const page = await screen.findByTitle(REVIEW);
      expect(page.getAttribute('src')).toBe(REVIEW_SRC);
      expect(page.hasAttribute('sandbox')).toBe(false);
      expect(steps().all).toEqual([
        'Upload (done)',
        'Detect (done)',
        'Review (in progress)',
        'Options (in progress)',
        'Build (not started)',
        'Walkthrough (not started)',
      ]);
      expect(steps().current).toEqual(['Review (in progress)']);

      const furnish = options().getByRole('checkbox', { name: 'Furnish the rooms' });
      if (!(furnish instanceof HTMLInputElement)) throw new Error('not a checkbox');
      expect(furnish.checked).toBe(true);
      expect(callsTo(fetchMock, 'POST', `${JOB}/embed`)).toHaveLength(1);
    });

    it("builds the quality choice from the server's list: Low, Medium and High, with High disabled and its reason shown", async () => {
      mockApi();
      renderJob();
      await screen.findByTitle(REVIEW);
      const radio = (name: string) => {
        const input = options().getByRole('radio', { name });
        if (!(input instanceof HTMLInputElement)) throw new Error(`${name} is not a radio button`);
        return input;
      };
      await options().findByRole('radio', { name: 'Medium' });
      expect(options().getAllByRole('radio')).toHaveLength(3);
      expect(options().getByRole('group', { name: 'Quality' })).toBeDefined();

      expect(radio('Low').checked).toBe(false);
      expect(radio('Low').disabled).toBe(false);
      expect(radio('Medium').checked).toBe(true); // the default
      expect(radio('Medium').disabled).toBe(false);
      expect(radio('High').checked).toBe(false);
      expect(radio('High').disabled).toBe(true);

      expect(options().getByText('Draft: the fastest build, to check the plan and walk through it.')).toBeDefined();
      expect(options().getByText('High-quality light and textures for the walkthrough.')).toBeDefined();
      const hint = document.getElementById(radio('High').getAttribute('aria-describedby') ?? '');
      expect(hint?.textContent).toBe('Cinema video tour of the house.Coming soon');

      fireEvent.click(radio('Low'));
      expect(radio('Low').checked).toBe(true);
      expect(radio('Medium').checked).toBe(false);
    });

    it('starts on Low when Medium cannot be built', async () => {
      const qualities = RAW_SYSTEM.qualities.map((quality) =>
        quality.id === 'medium' ? { ...quality, available: false, reason: 'The materials are still downloading.' } : quality,
      );
      mockApi({ [`GET ${BASE}/system`]: () => json({ ...RAW_SYSTEM, qualities }) });
      renderJob();
      await screen.findByTitle(REVIEW);
      const low = await options().findByRole('radio', { name: 'Low' });
      expect(low instanceof HTMLInputElement && low.checked).toBe(true);
      expect(isDisabled(options().getByRole('radio', { name: 'Medium' }))).toBe(true);
      expect(options().getByText('Not available: The materials are still downloading.')).toBeDefined();
    });

    it('offers to load the quality options again when they could not be loaded', async () => {
      mockApi({ [`GET ${BASE}/system`]: inTurn(() => json({ detail: 'Try again in a moment.' }, 503), () => json(RAW_SYSTEM)) });
      renderJob();
      await screen.findByTitle(REVIEW);
      const alert = await options().findByRole('alert');
      expect(alert.textContent).toContain('The quality options could not be loaded. Try again in a moment.');
      post(READY);
      expect(isDisabled(buildButton())).toBe(true); // nothing to build at yet
      fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
      await options().findByRole('radio', { name: 'Medium' });
      expect(isDisabled(buildButton())).toBe(false);
    });

    it('enables Build only once the review page of this job says the plan is loaded', async () => {
      mockApi();
      renderJob();
      await screen.findByTitle(REVIEW);
      await options().findByRole('radio', { name: 'Medium' });
      expect(isDisabled(buildButton())).toBe(true);
      expect(options().getByText(/the plan is still loading/i)).toBeDefined();

      // not from the API's origin
      post(READY, { origin: 'https://evil.example' });
      post(READY, { origin: window.location.origin });
      post(READY, { origin: '' });
      // not from the iframe of the review page
      post(READY, { source: anotherWindow() });
      // not the review page's protocol, or not this job
      post({ ...READY, source: 'someone-else' });
      post({ ...READY, job: 'ffffffffffff' });
      post({ type: 'ready' });
      post('ready');
      post(null);
      expect(isDisabled(buildButton())).toBe(true);

      post(READY);
      expect(isDisabled(buildButton())).toBe(false);
      expect(options().queryByText(/the plan is still loading/i)).toBeNull();
    });

    it('saves the plan through the review page, waits for its answer, then starts the build', async () => {
      let current = rawJob();
      const fetchMock = mockApi({
        [`GET ${JOB}`]: () => json(current),
        [`POST ${JOB}/build`]: () => {
          current = QUEUED;
          return json(current);
        },
      });
      const built = () => callsTo(fetchMock, 'POST', `${JOB}/build`);
      renderJob();
      const send = await openReview();

      fireEvent.click(buildButton());
      expect(send).toHaveBeenCalledTimes(1);
      expect(send).toHaveBeenCalledWith({ source: 'planto3d-host', type: 'save', furnish: true }, API);
      expect(isDisabled(buildButton())).toBe(true);
      expect(buildButton().getAttribute('aria-busy')).toBe('true');
      expect(options().getByText('Saving the plan and starting the build…')).toBeDefined();
      expect(built()).toHaveLength(0);

      // an answer is believed only from the API's origin, from this iframe, and for this job
      post(SAVED, { origin: 'https://evil.example' });
      post(SAVED, { source: anotherWindow() });
      post({ ...SAVED, job: 'ffffffffffff' });
      post({ ...SAVED, source: 'planto3d-host' });
      await act(async () => {
        await Promise.resolve();
      });
      expect(built()).toHaveLength(0);
      expect(isDisabled(buildButton())).toBe(true);

      post(SAVED);
      expect(await screen.findByRole('progressbar', { name: 'Build progress' })).toBeDefined();
      expect(built()).toHaveLength(1);
      expect(built()[0].url.href).toBe(`${API}${JOB}/build`);
      expect(JSON.parse(String(built()[0].init.body))).toEqual({ quality: 'medium' });
      expect(authorizationOf(built()[0])).toBe('Bearer test-jwt-token');
      expect(new Headers(built()[0].init.headers).get('Content-Type')).toBe('application/json');
      expect(send).toHaveBeenCalledTimes(1);

      // the build screen takes over
      expect(screen.getByRole('heading', { name: 'Waiting for the 3D builder' })).toBeDefined();
      expect(screen.getByText('2nd in the queue')).toBeDefined();
      expect(screen.getByText('Medium quality')).toBeDefined();
      expect(steps().current).toEqual(['Build (in progress)']);
    });

    it('sends the options the person chose', async () => {
      const fetchMock = mockApi({ [`POST ${JOB}/build`]: () => json({ ...QUEUED, quality: 'low' }) });
      renderJob();
      const send = await openReview();
      fireEvent.click(options().getByRole('checkbox', { name: 'Furnish the rooms' }));
      fireEvent.click(options().getByRole('radio', { name: 'Low' }));
      fireEvent.click(buildButton());
      expect(send).toHaveBeenCalledWith({ source: 'planto3d-host', type: 'save', furnish: false }, API);
      post(SAVED);
      await screen.findByRole('progressbar', { name: 'Build progress' });
      expect(JSON.parse(String(callsTo(fetchMock, 'POST', `${JOB}/build`)[0].init.body))).toEqual({ quality: 'low' });
      expect(screen.getByText('Low quality')).toBeDefined();
    });

    it('shows why the plan was not saved, and builds nothing', async () => {
      const fetchMock = mockApi();
      renderJob();
      await openReview();

      fireEvent.click(buildButton());
      post({ ...SAVED, ok: false, error: 'invalid plan' });
      expect((await options().findByRole('alert')).textContent).toBe('invalid plan');
      expect(isDisabled(buildButton())).toBe(false);

      // a refusal without a reason is still a refusal
      fireEvent.click(buildButton());
      expect(options().queryByRole('alert')).toBeNull();
      post({ source: 'planto3d', job: JOB_ID, type: 'saved', ok: false });
      expect((await options().findByRole('alert')).textContent).toBe('The plan could not be saved.');

      expect(callsTo(fetchMock, 'POST', `${JOB}/build`)).toHaveLength(0);
      expect(screen.getByTitle(REVIEW)).toBeDefined(); // still on the review step
    });

    it('gives up when the review page has not answered after 10 seconds', async () => {
      fakeClock();
      const fetchMock = mockApi({ [`POST ${JOB}/build`]: () => json(QUEUED) });
      const built = () => callsTo(fetchMock, 'POST', `${JOB}/build`);
      renderJob();
      await settle();
      post(READY);
      const send = vi.spyOn(pageOf(frame(REVIEW)), 'postMessage').mockImplementation(() => {});

      expect(SAVE_TIMEOUT_MS).toBe(10_000);
      fireEvent.click(buildButton());
      await advance(SAVE_TIMEOUT_MS - 1);
      expect(options().queryByRole('alert')).toBeNull();
      expect(isDisabled(buildButton())).toBe(true);
      await advance(1);
      expect(options().getByRole('alert').textContent).toBe(
        'The review page did not confirm that the plan was saved. Please try again.',
      );
      expect(isDisabled(buildButton())).toBe(false);
      expect(built()).toHaveLength(0);

      // an answer that comes too late starts nothing
      post(SAVED);
      await settle();
      expect(built()).toHaveLength(0);

      // trying again works
      fireEvent.click(buildButton());
      expect(send).toHaveBeenCalledTimes(2);
      post(SAVED);
      await settle();
      expect(built()).toHaveLength(1);
      expect(screen.getByRole('progressbar', { name: 'Build progress' })).toBeDefined();
    });

    it('says which reader made the plan, and builds only when the review page says it can be built', async () => {
      mockApi({});
      renderJob();
      await screen.findByTitle(REVIEW);
      await options().findByRole('radio', { name: 'Medium' });
      act(() =>
        post({ ...READY, reader: 'trace', notice: 'Neither reader could read this drawing.', buildable: false, problem: 'Draw the walls first.' }),
      );
      const note = await screen.findByRole('note', { name: 'How this plan was read' });
      expect(note.textContent).toContain('Trace the walls over the page');
      expect(note.textContent).toContain('Neither reader could read this drawing.');
      expect(isDisabled(buildButton())).toBe(true);
      expect(options().getByRole('alert').textContent).toBe('Draw the walls first.');

      act(() => post({ source: 'planto3d', job: JOB_ID, type: 'buildable', buildable: true, problem: null }));
      await waitFor(() => expect(isDisabled(buildButton())).toBe(false));
      expect(options().queryByRole('alert')).toBeNull();
    });

    it('names the AI plan reader', async () => {
      mockApi({});
      renderJob();
      await screen.findByTitle(REVIEW);
      act(() => post({ ...READY, reader: 'ai', notice: 'Read by the AI plan reader: check the walls, doors and sizes before you build.' }));
      const note = await screen.findByRole('note', { name: 'How this plan was read' });
      expect(note.textContent).toContain('read by the AI plan reader');
    });

    it('shows why the build could not be started', async () => {
      const fetchMock = mockApi({
        [`POST ${JOB}/build`]: inTurn(
          () => json({ detail: 'a build is already running' }, 409),
          () => json({ detail: HIGH_REASON }, 501),
        ),
      });
      renderJob();
      await openReview();
      fireEvent.click(buildButton());
      post(SAVED);
      expect((await options().findByRole('alert')).textContent).toBe('a build is already running');
      expect(isDisabled(buildButton())).toBe(false);

      fireEvent.click(buildButton());
      post(SAVED);
      await waitFor(() => expect(options().getByRole('alert').textContent).toBe(HIGH_REASON));
      expect(callsTo(fetchMock, 'POST', `${JOB}/build`)).toHaveLength(2);
      expect(screen.queryByRole('progressbar')).toBeNull();
    });

    it('offers to try again when the link of the review page cannot be made', async () => {
      const fetchMock = mockApi({
        [`POST ${JOB}/embed`]: inTurn(() => json({ detail: 'Try again in a moment.' }, 503), () => json(rawEmbed())),
      });
      renderJob();
      const alert = await screen.findByRole('alert');
      expect(alert.textContent).toContain('The plan could not be opened for review. Try again in a moment.');
      expect(screen.queryByTitle(REVIEW)).toBeNull();
      fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
      expect((await screen.findByTitle(REVIEW)).getAttribute('src')).toBe(REVIEW_SRC);
      expect(screen.queryByRole('alert')).toBeNull();
      expect(callsTo(fetchMock, 'POST', `${JOB}/embed`)).toHaveLength(2);
    });

    it('hands the open review page a fresh token before its own runs out', async () => {
      fakeClock();
      const fresh = `${BASE}/embed/a-newer-token`;
      mockApi({
        [`POST ${JOB}/embed`]: inTurn(() => json({ ...rawEmbed(), expires_in: 600 }), () => json(rawEmbed(JOB_ID, fresh))),
      });
      renderJob();
      await settle();
      post(READY);
      const old = frame(REVIEW);
      const send = vi.spyOn(pageOf(old), 'postMessage').mockImplementation(() => {});
      await advance(460_000); // past 75 % of the lifetime
      await settle();
      expect(send).toHaveBeenCalledWith({ source: 'planto3d-host', type: 'token', base: fresh }, API);
      expect(frame(REVIEW)).toBe(old); // the page was not reloaded
      await advance(200_000); // past the first token's end: still usable
      fireEvent.click(buildButton());
      expect(send).toHaveBeenCalledWith({ source: 'planto3d-host', type: 'save', furnish: true }, API);
    });

    it('asks for a new link when the one of the review page has run out', async () => {
      fakeClock();
      const fresh = `${BASE}/embed/a-newer-token`;
      const fetchMock = mockApi({
        [`POST ${JOB}/embed`]: inTurn(
          () => json({ ...rawEmbed(), expires_in: 600 }),
          () => json({ detail: 'Try again in a moment.' }, 503), // the refresh before expiry fails
          () => json(rawEmbed(JOB_ID, fresh)),
        ),
      });
      renderJob();
      await settle();
      post(READY);
      const old = frame(REVIEW);
      const send = vi.spyOn(pageOf(old), 'postMessage').mockImplementation(() => {});

      await advance(601_000);
      fireEvent.click(buildButton());
      expect(send).not.toHaveBeenCalled(); // the page could not save any more
      const alert = options().getByRole('alert');
      expect(alert.textContent).toMatch(/open for too long/i);

      fireEvent.click(within(alert).getByRole('button', { name: 'Open the plan again' }));
      await settle();
      expect(callsTo(fetchMock, 'POST', `${JOB}/embed`)).toHaveLength(3);
      expect(frame(REVIEW).getAttribute('src')).toBe(`${API}${fresh}/web/edit.html?job=${JOB_ID}&embed`);
      expect(frame(REVIEW)).not.toBe(old);
      // a new page: it has to say that the plan is loaded before it can be built
      expect(options().queryByRole('alert')).toBeNull();
      expect(isDisabled(buildButton())).toBe(true);
    });
  });

  // ------------------------------------------------------------------- build

  describe('while the house is built', () => {
    it('shows the place in the queue, then the progress with the time left, until the walkthrough opens', async () => {
      fakeClock();
      const building = (progress: number, etaLeft: number, message: string) =>
        rawJob({ stage: 'building', progress, message, quality: 'medium', eta_left: etaLeft });
      const fetchMock = mockApi({
        [`GET ${JOB}`]: statuses(
          QUEUED,
          { ...QUEUED, queue_position: 1, message: 'Waiting for the 3D builder (0 ahead)' },
          building(45, 120, 'Baking the light'),
          building(95, 10, 'Exporting'),
          DONE,
        ),
      });
      const asked = () => callsTo(fetchMock, 'GET', JOB).length;
      renderJob();
      await settle();

      const bar = () => screen.getByRole('progressbar', { name: 'Build progress' });
      expect(screen.getByRole('heading', { name: 'Waiting for the 3D builder' })).toBeDefined();
      expect(bar().hasAttribute('aria-valuenow')).toBe(false);
      expect(screen.getByRole('status').textContent).toBe('Waiting for the 3D builder (1 ahead)');
      expect(screen.getByText('2nd in the queue')).toBeDefined();
      expect(screen.getByText('Medium quality')).toBeDefined();
      expect(steps().all).toEqual([
        'Upload (done)',
        'Detect (done)',
        'Review (done)',
        'Options (done)',
        'Build (in progress)',
        'Walkthrough (not started)',
      ]);

      await advance(PLAN3D_POLL_MS);
      expect(screen.getByText('Next in the queue')).toBeDefined();

      await advance(PLAN3D_POLL_MS);
      expect(screen.getByRole('heading', { name: 'Building the 3D house' })).toBeDefined();
      expect(bar().getAttribute('aria-valuenow')).toBe('45');
      expect(screen.getByText('45%')).toBeDefined();
      expect(screen.getByRole('status').textContent).toBe('Baking the light');
      expect(screen.getByText('about 2 min left')).toBeDefined();
      expect(screen.getByText('Medium quality')).toBeDefined();
      expect(screen.queryByText(/in the queue/)).toBeNull();

      await advance(PLAN3D_POLL_MS);
      expect(bar().getAttribute('aria-valuenow')).toBe('95');
      expect(screen.getByText('almost done')).toBeDefined();
      // nothing with an iframe was on screen so far
      expect(callsTo(fetchMock, 'POST', `${JOB}/embed`)).toHaveLength(0);
      expect(asked()).toBe(4);

      await advance(PLAN3D_POLL_MS);
      await settle();
      expect(frame(WALK).getAttribute('src')).toBe(WALK_SRC);
      expect(screen.queryByRole('progressbar')).toBeNull();
      expect(steps().current).toEqual(['Walkthrough (in progress)']);

      // the house is done: nothing is asked any more, and the link was asked for once
      await advance(PLAN3D_POLL_MS * 6);
      expect(asked()).toBe(5);
      expect(callsTo(fetchMock, 'POST', `${JOB}/embed`)).toHaveLength(1);
    });
  });

  describe('when the build failed', () => {
    it('shows why, with a way back to the review and to all plans', async () => {
      const fetchMock = mockApi({ [`GET ${JOB}`]: () => json(BUILD_FAILED) });
      renderJob();
      expect((await screen.findByRole('alert')).textContent).toBe('3D build failed - see build.log');
      expect(screen.getByRole('heading', { name: 'The 3D build failed' })).toBeDefined();
      expect(screen.getByRole('link', { name: 'Back to all plans' }).getAttribute('href')).toBe('/3d');
      expect(steps().current).toEqual(['Build (failed)']);
      expect(screen.queryByTitle(REVIEW)).toBeNull();
      expect(callsTo(fetchMock, 'POST', `${JOB}/embed`)).toHaveLength(0);

      fireEvent.click(screen.getByRole('button', { name: 'Review the plan again' }));
      expect((await screen.findByTitle(REVIEW)).getAttribute('src')).toBe(REVIEW_SRC);
      expect(screen.getByRole('region', { name: 'Build options' })).toBeDefined();
      expect(screen.queryByRole('heading', { name: 'The 3D build failed' })).toBeNull();
      expect(steps().current).toEqual(['Review (in progress)']);

      fireEvent.click(options().getByRole('button', { name: 'Cancel' }));
      expect(screen.getByRole('heading', { name: 'The 3D build failed' })).toBeDefined();
    });

    it('keeps the review page through the build, so the plan comes back as it was left', async () => {
      fakeClock();
      let current = rawJob();
      const fetchMock = mockApi({
        [`GET ${JOB}`]: () => json(current),
        [`POST ${JOB}/build`]: () => {
          current = QUEUED;
          return json(current);
        },
      });
      renderJob();
      await settle();
      post(READY);
      const page = frame(REVIEW);
      vi.spyOn(pageOf(page), 'postMessage').mockImplementation(() => {});
      const section = () => screen.getByTitle(REVIEW).closest('section');

      fireEvent.click(buildButton());
      post(SAVED);
      await settle();
      expect(screen.getByRole('progressbar', { name: 'Build progress' })).toBeDefined();
      // out of sight, but the very same page
      expect(screen.getByTitle(REVIEW)).toBe(page);
      expect(section()?.hasAttribute('hidden')).toBe(true);
      expect(screen.queryByRole('region', { name: 'Build options' })).toBeNull();

      current = BUILD_FAILED;
      await advance(PLAN3D_POLL_MS);
      expect(screen.getByRole('alert').textContent).toBe('3D build failed - see build.log');
      expect(section()?.hasAttribute('hidden')).toBe(true);

      fireEvent.click(screen.getByRole('button', { name: 'Review the plan again' }));
      expect(screen.getByTitle(REVIEW)).toBe(page);
      expect(section()?.hasAttribute('hidden')).toBe(false);
      expect(isDisabled(buildButton())).toBe(false); // the plan is still loaded in it
      expect(callsTo(fetchMock, 'POST', `${JOB}/embed`)).toHaveLength(1); // and no new link was asked for
    });

    it('says so when the review page cannot open the plan', async () => {
      mockApi({ [`GET ${JOB}`]: () => json(BUILD_FAILED) });
      renderJob();
      fireEvent.click(await screen.findByRole('button', { name: 'Review the plan again' }));
      await screen.findByTitle(REVIEW);
      await options().findByRole('radio', { name: 'Medium' });
      post({ source: 'planto3d', job: JOB_ID, type: 'failed', message: '3D build failed - see build.log' });
      expect(options().getByRole('alert').textContent).toBe(
        'The plan could not be opened for review. 3D build failed - see build.log',
      );
      expect(isDisabled(buildButton())).toBe(true);
    });
  });

  // ------------------------------------------------------------- walkthrough

  describe('when the house is built', () => {
    const done = (routes: MockRoutes = {}) => mockApi({ [`GET ${JOB}`]: () => json(DONE), ...routes });

    it('shows the walkthrough in an iframe, with the quality and how long the build took', async () => {
      const fetchMock = done();
      renderJob();
      const walkthrough = await screen.findByTitle(WALK);
      expect(walkthrough.getAttribute('src')).toBe(WALK_SRC);
      expect(walkthrough.getAttribute('allow')).toBe('fullscreen');
      expect(walkthrough.hasAttribute('sandbox')).toBe(false);
      expect(screen.getByText('Built at Medium quality in 3 min 20 s')).toBeDefined();
      expect(steps().all).toEqual([
        'Upload (done)',
        'Detect (done)',
        'Review (done)',
        'Options (done)',
        'Build (done)',
        'Walkthrough (in progress)',
      ]);
      expect(screen.getByRole('link', { name: 'Furniture models' }).getAttribute('href')).toBe('/3d/furniture');
      expect(screen.getByRole('button', { name: 'Full screen' })).toBeDefined();
      expect(screen.queryByTitle(REVIEW)).toBeNull();
      expect(callsTo(fetchMock, 'POST', `${JOB}/embed`)).toHaveLength(1);
    });

    it('goes full screen on the box around the walkthrough', async () => {
      done();
      renderJob();
      const box = (await screen.findByTitle(WALK)).parentElement;
      if (!box) throw new Error('the walkthrough has no box');
      // jsdom has no full screen: the button must not throw without it
      fireEvent.click(screen.getByRole('button', { name: 'Full screen' }));
      const request = vi.fn(() => Promise.reject(new Error('refused')));
      Object.defineProperty(box, 'requestFullscreen', { configurable: true, value: request });
      fireEvent.click(screen.getByRole('button', { name: 'Full screen' }));
      expect(request).toHaveBeenCalledTimes(1);
    });

    it('packs the Blender file, then starts its download from a link made at that moment', async () => {
      const downloads: string[] = [];
      vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
        downloads.push(this.href);
      });
      let packed: (answer: Response) => void = () => {};
      const fresh = `${BASE}/embed/a-newer-token`;
      const fetchMock = done({
        [`POST ${JOB}/export`]: () => new Promise<Response>((resolve) => (packed = resolve)),
        [`POST ${JOB}/embed`]: inTurn(() => json(rawEmbed()), () => json(rawEmbed(JOB_ID, fresh))),
      });
      renderJob();
      const walkthrough = await screen.findByTitle(WALK);
      const button = () => screen.getByRole('button', { name: 'Download Blender file' });

      fireEvent.click(button());
      expect(isDisabled(button())).toBe(true);
      expect(button().getAttribute('aria-busy')).toBe('true');
      expect(screen.getByText(/packing the blender file/i).getAttribute('role')).toBe('status');
      await waitFor(() => expect(callsTo(fetchMock, 'POST', `${JOB}/export`)).toHaveLength(1));
      expect(authorizationOf(callsTo(fetchMock, 'POST', `${JOB}/export`)[0])).toBe('Bearer test-jwt-token');
      expect(downloads).toEqual([]);

      packed(json({ file: 'house_blender.zip' }));
      await waitFor(() => expect(downloads).toEqual([`${API}${fresh}/jobs/${JOB_ID}/house_blender.zip`]));
      await waitFor(() => expect(isDisabled(button())).toBe(false));
      expect(screen.queryByText(/packing the blender file/i)).toBeNull();
      expect(screen.queryByRole('alert')).toBeNull();
      // the walkthrough itself was left alone
      expect(screen.getByTitle(WALK)).toBe(walkthrough);
      expect(walkthrough.getAttribute('src')).toBe(WALK_SRC);
    });

    it('says why the Blender file could not be made', async () => {
      const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
      done({ [`POST ${JOB}/export`]: () => json({ detail: 'Blender is busy.' }, 503) });
      renderJob();
      await screen.findByTitle(WALK);
      fireEvent.click(screen.getByRole('button', { name: 'Download Blender file' }));
      expect((await screen.findByRole('alert')).textContent).toBe('The Blender file could not be prepared. Blender is busy.');
      expect(click).not.toHaveBeenCalled();
      expect(isDisabled(screen.getByRole('button', { name: 'Download Blender file' }))).toBe(false);
    });

    it('makes a share link, copies it, and turns it off', async () => {
      const link = `${BASE}/embed/a-share-token/web/view.html?job=${JOB_ID}&shared`;
      const writeText = vi.fn(() => Promise.resolve());
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
      const fetchMock = done({
        [`POST ${JOB}/share`]: () => json({ url: link, expires_in: 2592000 }),
        [`DELETE ${JOB}/share`]: () => noContent(),
      });
      renderJob();
      await screen.findByTitle(WALK);

      fireEvent.click(screen.getByRole('button', { name: 'Share walkthrough' }));
      const field = (await screen.findByRole('textbox', { name: 'Share link to the walkthrough' })) as HTMLInputElement;
      expect(field.value).toBe(`${API}${link}`);
      expect(writeText).toHaveBeenCalledWith(`${API}${link}`);
      expect(await screen.findByText(/Copied\. Anyone with this link can walk through the house/)).toBeDefined();
      expect(authorizationOf(callsTo(fetchMock, 'POST', `${JOB}/share`)[0])).toBe('Bearer test-jwt-token');
      expect(screen.getByRole('button', { name: 'New share link' })).toBeDefined();

      fireEvent.click(screen.getByRole('button', { name: 'Turn link off' }));
      await waitFor(() => expect(callsTo(fetchMock, 'DELETE', `${JOB}/share`)).toHaveLength(1));
      await waitFor(() => expect(screen.queryByRole('textbox', { name: 'Share link to the walkthrough' })).toBeNull());
      expect(screen.getByRole('button', { name: 'Share walkthrough' })).toBeDefined();
    });

    it('deletes the plan after a confirm, then goes back to all plans', async () => {
      const fetchMock = done({ [`DELETE ${JOB}`]: () => noContent() });
      const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
      renderJob();
      await screen.findByTitle(WALK);

      fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
      expect(String(confirm.mock.calls[0][0])).toContain('green-villa.pdf');
      expect(callsTo(fetchMock, 'DELETE', JOB)).toHaveLength(0);
      expect(screen.getByTitle(WALK)).toBeDefined();

      confirm.mockReturnValue(true);
      fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
      expect(await screen.findByText('all plans page')).toBeDefined();
      expect(authorizationOf(callsTo(fetchMock, 'DELETE', JOB)[0])).toBe('Bearer test-jwt-token');
    });

    it('stays on the page when the plan cannot be deleted', async () => {
      done({ [`DELETE ${JOB}`]: () => json({ detail: 'a build is already running' }, 409) });
      vi.spyOn(window, 'confirm').mockReturnValue(true);
      renderJob();
      await screen.findByTitle(WALK);
      fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
      expect((await screen.findByRole('alert')).textContent).toBe('The plan could not be deleted. a build is already running');
      expect(screen.getByTitle(WALK)).toBeDefined();
      expect(screen.queryByText('all plans page')).toBeNull();
    });

    it('opens the review and the options again to change the plan, and builds it once more', async () => {
      let current: unknown = DONE;
      const fetchMock = mockApi({
        [`GET ${JOB}`]: () => json(current),
        [`POST ${JOB}/build`]: () => {
          current = { ...QUEUED, queue_position: 1 };
          return json(current);
        },
      });
      renderJob();
      await screen.findByTitle(WALK);

      fireEvent.click(screen.getByRole('button', { name: 'Edit plan and rebuild' }));
      expect(screen.queryByTitle(WALK)).toBeNull();
      expect((await screen.findByTitle(REVIEW)).getAttribute('src')).toBe(REVIEW_SRC);
      expect(steps().current).toEqual(['Review (in progress)']);

      // back without building
      fireEvent.click(options().getByRole('button', { name: 'Back to the walkthrough' }));
      expect((await screen.findByTitle(WALK)).getAttribute('src')).toBe(WALK_SRC);
      expect(screen.queryByTitle(REVIEW)).toBeNull();

      fireEvent.click(screen.getByRole('button', { name: 'Edit plan and rebuild' }));
      const send = await openReview();
      fireEvent.click(buildButton());
      expect(send).toHaveBeenCalledWith({ source: 'planto3d-host', type: 'save', furnish: true }, API);
      post(SAVED);
      expect(await screen.findByRole('progressbar', { name: 'Build progress' })).toBeDefined();
      expect(screen.getByText('Next in the queue')).toBeDefined();
      expect(callsTo(fetchMock, 'POST', `${JOB}/build`)).toHaveLength(1);
    });

    it('offers to try again when the link of the walkthrough cannot be made', async () => {
      done({ [`POST ${JOB}/embed`]: inTurn(() => json({ detail: 'Try again in a moment.' }, 503), () => json(rawEmbed())) });
      renderJob();
      const alert = await screen.findByRole('alert');
      expect(alert.textContent).toContain('The walkthrough could not be opened. Try again in a moment.');
      expect(screen.queryByTitle(WALK)).toBeNull();
      fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
      expect((await screen.findByTitle(WALK)).getAttribute('src')).toBe(WALK_SRC);
      expect(screen.queryByRole('alert')).toBeNull();
    });
  });

  // ------------------------------------------------------------------- other

  describe('a plan that cannot be shown', () => {
    it('says that the plan was not found, with a link to all plans', async () => {
      fakeClock();
      const fetchMock = mockApi({ [`GET ${JOB}`]: () => json({ detail: '3D job not found.' }, 404) });
      renderJob();
      await settle();
      expect(screen.getByRole('heading', { name: 'This plan was not found' })).toBeDefined();
      expect(screen.getByRole('link', { name: 'Back to all plans' }).getAttribute('href')).toBe('/3d');
      expect(screen.queryByRole('list', { name: 'Steps' })).toBeNull();
      // it is not asked for again, and nothing else is tried with it
      await advance(PLAN3D_POLL_MS * 6);
      expect(callsTo(fetchMock, 'GET', JOB)).toHaveLength(1);
      expect(callsTo(fetchMock, 'POST', `${JOB}/embed`)).toHaveLength(0);
    });

    it('offers to load the plan again when the server could not be asked', async () => {
      mockApi({ [`GET ${JOB}`]: inTurn(() => json({ detail: 'The 3D builder is not running right now.' }, 503), () => json(DONE)) });
      renderJob();
      const alert = await screen.findByRole('alert');
      expect(alert.textContent).toContain('The 3D builder is not running right now.');
      expect(screen.queryByText('This plan was not found')).toBeNull();
      fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
      expect(await screen.findByTitle(WALK)).toBeDefined();
    });
  });

  describe('who is told what', () => {
    it('sends the session token with every API call, and none with the pages in the iframes', async () => {
      const fetchMock = mockApi({ [`GET ${JOB}`]: () => json(DONE) });
      renderJob();
      const walkthrough = await screen.findByTitle(WALK);
      await waitFor(() => expect(callsTo(fetchMock, 'GET', `${BASE}/system`)).toHaveLength(1));

      const requests = fetchMock.mock.calls.map(([input, init]) => ({ url: new URL(String(input)), init: init ?? {} }));
      expect(requests.map(({ url, init }) => `${init.method ?? 'GET'} ${url.pathname}`).sort()).toEqual(
        [`GET ${BASE}/system`, `GET ${JOB}`, `POST ${JOB}/embed`].sort(),
      );
      for (const request of requests) expect(authorizationOf(request), request.url.pathname).toBe('Bearer test-jwt-token');

      // the iframe is given a URL and nothing else: the signed token in its path stands in for the header
      const src = walkthrough.getAttribute('src') ?? '';
      expect(src).toBe(`${API}${BASE}/embed/${TOKEN}/web/view.html?job=${JOB_ID}&embed`);
      expect(src).not.toContain('test-jwt-token');
      expect(Array.from(new URL(src).searchParams.keys())).toEqual(['job', 'embed']);
      // and the app itself never fetches such a URL
      expect(requests.some(({ url }) => url.pathname.startsWith(`${BASE}/embed/`))).toBe(false);
    });
  });
});

describe('Low preview while High builds', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(TOKEN_STORAGE_KEY, 'test-jwt-token');
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('shows the Low house to walk through while High builds, then the finished walkthrough', async () => {
    fakeClock();
    mockApi({
      [`GET ${JOB}`]: statuses(rawJob({ stage: 'building', quality: 'high', progress: 40, preview: true }), DONE),
      [`POST ${JOB}/embed`]: () => json(rawEmbed()),
    });
    renderJob();
    await settle();
    expect(screen.getByRole('progressbar', { name: 'Build progress' })).toBeDefined();
    expect(screen.getByTitle('3D walkthrough preview')).toBeDefined();
    await advance(PLAN3D_POLL_MS);
    await settle();
    expect(screen.queryByTitle('3D walkthrough preview')).toBeNull();
    expect(screen.getByTitle('3D walkthrough')).toBeDefined();
  });
});

describe('video tours', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(TOKEN_STORAGE_KEY, 'test-jwt-token');
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('asks for a tour of the built house and offers a finished one for download', async () => {
    fakeClock();
    const fetchMock = mockApi({
      [`GET ${JOB}`]: () => json({ ...DONE, tours: { high: { file: 'tour_high.mp4', seconds: 300 } } }),
      [`POST ${JOB}/embed`]: () => json(rawEmbed()),
      [`POST ${JOB}/tour`]: () => json(rawJob({ stage: 'queued', quality: 'medium' })),
    });
    renderJob();
    await settle();
    const tours = screen.getByRole('group', { name: 'Video tour' });
    expect(within(tours).getByRole('button', { name: /High \(720p\) video/ })).toBeDefined();
    fireEvent.click(within(tours).getByRole('button', { name: 'Render Ultra (1080p)' }));
    await settle();
    const [asked] = callsTo(fetchMock, 'POST', `${JOB}/tour`);
    expect(JSON.parse(String(asked.init.body))).toEqual({ quality: 'ultra' });
    expect(screen.getByRole('progressbar', { name: 'Build progress' })).toBeDefined();
  });
});
