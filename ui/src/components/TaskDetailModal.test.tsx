import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { TaskDetailModal } from './TaskDetailModal';

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api');
  return {
    ...actual,
    api: {
      getTask: vi.fn(),
      patchTask: vi.fn(),
      startTaskSession: vi.fn(),
      listWorktrees: vi.fn(),
    },
  };
});

import { api } from '../lib/api';

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getTask).mockResolvedValue({
    id: 't1', project_id: 'p1', title: 'X', description: 'D',
    state: 'ready', template: null, permission_profile: null, branch: null,
    created_at: '', updated_at: '', active_session_id: null,
  });
  vi.mocked(api.patchTask).mockResolvedValue({} as never);
  vi.mocked(api.startTaskSession).mockResolvedValue({} as never);
  vi.mocked(api.listWorktrees).mockResolvedValue([
    {
      id: 'w1',
      repository_id: 'r1',
      repository_name: 'projA',
      task_id: null,
      branch: 'main',
      path: '/r',
      is_orphan: true,
    },
  ]);
});

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('TaskDetailModal', () => {
  it('lists only valid Move-to states from current state ready', async () => {
    wrap(<TaskDetailModal taskId="t1" onClose={() => {}} />);
    await screen.findByDisplayValue('X');
    const select = screen.getByLabelText(/move to/i) as HTMLSelectElement;
    const opts = Array.from(select.options).map((o) => o.value).filter(Boolean);
    // ready → idea, in_progress, discarded
    expect(opts).toEqual(expect.arrayContaining(['idea', 'in_progress', 'discarded']));
    expect(opts).not.toContain('done');
    expect(opts).not.toContain('review');
  });

  it('disables iniciar sessão when state is done', async () => {
    vi.mocked(api.getTask).mockResolvedValueOnce({
      id: 't1', project_id: 'p1', title: 'X', description: '',
      state: 'done', template: null, permission_profile: null, branch: null,
      created_at: '', updated_at: '', active_session_id: null,
    });
    wrap(<TaskDetailModal taskId="t1" onClose={() => {}} />);
    const btn = await screen.findByRole('button', { name: /iniciar sessão/i });
    expect(btn).toBeDisabled();
  });

  it('disables iniciar sessão when state is discarded', async () => {
    vi.mocked(api.getTask).mockResolvedValueOnce({
      id: 't1', project_id: 'p1', title: 'X', description: '',
      state: 'discarded', template: null, permission_profile: null, branch: null,
      created_at: '', updated_at: '', active_session_id: null,
    });
    wrap(<TaskDetailModal taskId="t1" onClose={() => {}} />);
    const btn = await screen.findByRole('button', { name: /iniciar sessão/i });
    expect(btn).toBeDisabled();
  });

  it('debounces title PATCH (single call after rapid changes)', async () => {
    wrap(<TaskDetailModal taskId="t1" onClose={() => {}} />);
    const input = (await screen.findByDisplayValue('X')) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Y' } });
    fireEvent.change(input, { target: { value: 'Y2' } });
    await waitFor(
      () => expect(api.patchTask).toHaveBeenCalledTimes(1),
      { timeout: 1500 },
    );
    expect(api.patchTask).toHaveBeenLastCalledWith('t1', { title: 'Y2' });
  });

  it('Move-to dropdown PATCH calls', async () => {
    wrap(<TaskDetailModal taskId="t1" onClose={() => {}} />);
    await screen.findByDisplayValue('X');
    const select = screen.getByLabelText(/move to/i) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'in_progress' } });
    await waitFor(() => {
      expect(api.patchTask).toHaveBeenCalledWith('t1', { state: 'in_progress' });
    });
  });

  it('iniciar sessão calls startTaskSession with task id', async () => {
    wrap(<TaskDetailModal taskId="t1" onClose={() => {}} />);
    await screen.findByDisplayValue('X');
    const wtSelect = screen.getByLabelText(/worktree/i) as HTMLSelectElement;
    fireEvent.change(wtSelect, { target: { value: 'w1' } });
    const btn = screen.getByRole('button', { name: /iniciar sessão/i });
    fireEvent.click(btn);
    await waitFor(() => {
      expect(api.startTaskSession).toHaveBeenCalledWith('t1');
    });
  });
});
