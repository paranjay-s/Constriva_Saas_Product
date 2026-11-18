/**
 * The 2D-to-3D import screen: a failed parse shows the parser's error with a retry, and no
 * other plan is ever shown in place of the one that failed.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../../context/AuthContext';
import { ProjectProvider } from '../../context/ProjectContext';
import { ImportPlanPage } from './ImportPlanPage';
import { filesApi, type ParsingProgressEvent } from './api';

type Callbacks = Parameters<typeof filesApi.subscribeToProgress>[1];

const PLAN = {
  schema_version: '2.0',
  units: 'm',
  levels: [
    {
      rooms: [
        { id: 'L0-R01', name: 'BEDROOM', polygon: [[0, 0], [4, 0], [4, 5], [0, 5]] },
        { id: 'L0-R02', name: 'KITCHEN', polygon: [[4, 0], [8, 0], [8, 5], [4, 5]] },
      ],
      walls: [{ id: 'L0-W01', start: [0, 0], end: [8, 0] }],
      openings: [],
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <ProjectProvider>
          <ImportPlanPage />
        </ProjectProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

function pickPdf(name = 'house.pdf') {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File([new Uint8Array([37, 80, 68, 70])], name, { type: 'application/pdf' });
  fireEvent.change(input, { target: { files: [file] } });
}

describe('ImportPlanPage', () => {
  let callbacks: Callbacks;
  let upload: ReturnType<typeof vi.spyOn>;
  let projectPlan: ReturnType<typeof vi.spyOn>;
  let planById: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    upload = vi
      .spyOn(filesApi, 'uploadBlueprint')
      .mockResolvedValue({ task_id: 'task-1', project_id: 'p1', status: 'queued', stream_url: '', message: '' });
    vi.spyOn(filesApi, 'subscribeToProgress').mockImplementation((_taskId, cbs) => {
      callbacks = cbs;
      return () => {};
    });
    projectPlan = vi.spyOn(filesApi, 'getProjectPlan');
    planById = vi.spyOn(filesApi, 'getPlanById').mockResolvedValue({ id: 'plan-1', name: 'Plan', plan_json: PLAN } as never);
  });

  async function startUpload() {
    renderPage();
    pickPdf();
    fireEvent.click(screen.getByRole('button', { name: /process architectural plan/i }));
    await waitFor(() => expect(upload).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(callbacks).toBeDefined());
  }

  it('shows the parser error with a retry, and substitutes no plan', async () => {
    await startUpload();
    act(() => callbacks.onError('The floor plan could not be read reliably from this drawing.', 'llm_output_invalid'));

    expect(await screen.findByText(/the plan could not be processed/i)).toBeDefined();
    expect(screen.getByText(/could not be read reliably from this drawing/i)).toBeDefined();
    expect(screen.getByText(/nothing was saved\. try again, or use a clearer pdf/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /try again/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /choose another file/i })).toBeDefined();
    // no completed state, and no other plan was fetched to stand in for the failed one
    expect(screen.queryByText(/plan processed successfully/i)).toBeNull();
    expect(screen.queryByRole('button', { name: /open 3d workspace/i })).toBeNull();
    expect(projectPlan).not.toHaveBeenCalled();
    expect(planById).not.toHaveBeenCalled();
  });

  it('retries the same file and then shows the real counts of the plan that was made', async () => {
    await startUpload();
    act(() => callbacks.onError('The AI service did not respond.', 'llm_unavailable'));
    fireEvent.click(await screen.findByRole('button', { name: /try again/i }));
    await waitFor(() => expect(upload).toHaveBeenCalledTimes(2));
    expect((upload.mock.calls[1][0] as File).name).toBe('house.pdf');

    const done: ParsingProgressEvent = {
      task_id: 'task-1',
      status: 'done',
      progress: 100,
      step: 'done',
      result: { plan_id: 'plan-1', project_id: 'p1' },
    };
    await act(async () => {
      await callbacks.onComplete(done);
    });

    expect(await screen.findByText(/plan processed successfully/i)).toBeDefined();
    expect(planById).toHaveBeenCalledWith('plan-1');
    expect(projectPlan).not.toHaveBeenCalled();
    // counts come from the plan itself: 2 rooms, 1 wall, 0 openings
    const counts = Array.from(document.querySelectorAll('.grid.grid-cols-3 .font-mono.text-lg')).map((n) => n.textContent);
    expect(counts).toEqual(['2', '1', '0']);
  });

  it('never loads a plan from the browser by file name', async () => {
    localStorage.setItem('construtiva_plan_cache_house.pdf', JSON.stringify({ levels: [{ rooms: [{ id: 'other' }] }] }));
    localStorage.setItem('construtiva_plan_cache_house.pdf_4', JSON.stringify({ levels: [{ rooms: [{ id: 'other' }] }] }));
    await startUpload();
    // the file was uploaded instead of being answered from a same-named cache entry
    expect(upload).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/instant load/i)).toBeNull();
    expect(screen.queryByText(/plan processed successfully/i)).toBeNull();
  });

  it('lets the user choose another file after a failure', async () => {
    await startUpload();
    act(() => callbacks.onError('No floor plan was found in this PDF.', 'no_floor_plan'));
    fireEvent.click(await screen.findByRole('button', { name: /choose another file/i }));
    expect(await screen.findByText(/drag and drop your architectural pdf here/i)).toBeDefined();
    expect(screen.queryByText(/the plan could not be processed/i)).toBeNull();
  });

  it('reports a finished job whose plan cannot be loaded as an error, not as success', async () => {
    planById.mockRejectedValueOnce(new Error('404'));
    await startUpload();
    await act(async () => {
      await callbacks.onComplete({ task_id: 'task-1', status: 'done', progress: 100, step: 'done', result: { plan_id: 'plan-1' } });
    });
    expect(await screen.findByText(/was processed but could not be loaded/i)).toBeDefined();
    expect(screen.queryByText(/plan processed successfully/i)).toBeNull();
    expect(projectPlan).not.toHaveBeenCalled();
  });
});
