import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { OverviewTab } from './OverviewTab';
import type { Task } from '../../lib/api';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual('../../lib/api');
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

import { api } from '../../lib/api';

const BASE_TASK: Task = {
  id: 't1', project_id: 'p1', title: 'X', description: 'D',
  state: 'ready', template: null, permission_profile: null, branch: null,
  created_at: '', updated_at: '', active_session_id: null,
};

beforeEach(() => {
  vi.clearAllMocks();
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

function wrap(task: Task = BASE_TASK) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <OverviewTab task={task} />
    </QueryClientProvider>,
  );
}

describe('OverviewTab', () => {
  it('lists only valid Move-to states from current state ready', async () => {
    wrap();
    await screen.findByDisplayValue('X');
    const select = screen.getByLabelText(/move to/i) as HTMLSelectElement;
    const opts = Array.from(select.options).map((o) => o.value).filter(Boolean);
    // ready → idea, in_progress, discarded
    expect(opts).toEqual(expect.arrayContaining(['idea', 'in_progress', 'discarded']));
    expect(opts).not.toContain('done');
    expect(opts).not.toContain('review');
  });

  it('disables iniciar sessão when state is done', async () => {
    wrap({ ...BASE_TASK, state: 'done', description: '' });
    const btn = await screen.findByRole('button', { name: /iniciar sessão/i });
    expect(btn).toBeDisabled();
  });

  it('disables iniciar sessão when state is discarded', async () => {
    wrap({ ...BASE_TASK, state: 'discarded', description: '' });
    const btn = await screen.findByRole('button', { name: /iniciar sessão/i });
    expect(btn).toBeDisabled();
  });

  it('debounces title PATCH (single call after rapid changes)', async () => {
    wrap();
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
    wrap();
    await screen.findByDisplayValue('X');
    const select = screen.getByLabelText(/move to/i) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'in_progress' } });
    await waitFor(() => {
      expect(api.patchTask).toHaveBeenCalledWith('t1', { state: 'in_progress' });
    });
  });

  it('iniciar sessão calls startTaskSession with task id', async () => {
    wrap();
    await screen.findByDisplayValue('X');
    const btn = screen.getByRole('button', { name: /iniciar sessão/i });
    fireEvent.click(btn);
    await waitFor(() => {
      expect(api.startTaskSession).toHaveBeenCalledWith('t1');
    });
  });

  it('shows task config section with template + profile + branch', async () => {
    wrap({
      ...BASE_TASK,
      template: 'frontend',
      permission_profile: 'yolo',
      branch: 'feat-ui/foo',
      description: '',
    });
    await screen.findByDisplayValue('X');
    const section = screen.getByLabelText('task-config');
    expect(section).toHaveTextContent('frontend');
    expect(section).toHaveTextContent('yolo');
    expect(section).toHaveTextContent('feat-ui/foo');
  });

  it('shows fallback labels when template/profile/branch are null', async () => {
    wrap();
    await screen.findByDisplayValue('X');
    const section = screen.getByLabelText('task-config');
    expect(section).toHaveTextContent('(nenhum)');
    expect(section).toHaveTextContent('(fallback)');
    expect(section).toHaveTextContent('(será derivado no spawn)');
  });
});
