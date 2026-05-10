import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { ProjectNode } from './ProjectNode';
import type { Project, Task, Worktree } from '../lib/api';

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api');
  return {
    ...actual,
    api: {
      listWorktrees: vi.fn(),
      listTasks: vi.fn(),
      deleteProject: vi.fn(),
      deleteWorktree: vi.fn(),
    },
  };
});

import { api } from '../lib/api';

const monorepoProject: Project = {
  id: 'p1',
  name: 'gcb-financeiro',
  path: '/p',
  created_at: '',
  repositories: [{ id: 'r1', name: 'gcb-financeiro', sub_path: '.' }],
};

const multiRepoProject: Project = {
  id: 'p2',
  name: 'gcb-hub',
  path: '/q',
  created_at: '',
  repositories: [
    { id: 'r2', name: 'backend', sub_path: 'backend' },
    { id: 'r3', name: 'frontend', sub_path: 'frontend' },
  ],
};

const task = (id: string, state: string, title: string): Task => ({
  id,
  project_id: 'p1',
  title,
  description: '',
  state,
  template: null,
  permission_profile: null,
  branch: null,
  created_at: '',
  updated_at: '',
  active_session_id: null,
});

const wt = (id: string, taskId: string | null, branch: string): Worktree => ({
  id,
  repository_id: 'r1',
  repository_name: 'gcb-financeiro',
  task_id: taskId,
  path: `/p/${branch}`,
  branch,
  is_orphan: taskId === null,
});

beforeEach(() => {
  vi.clearAllMocks();
  // Each test sets specific return values via mockResolvedValueOnce.
  vi.mocked(api.listWorktrees).mockResolvedValue([]);
  vi.mocked(api.listTasks).mockResolvedValue([]);
  vi.mocked(api.deleteProject).mockResolvedValue(undefined);
  vi.mocked(api.deleteWorktree).mockResolvedValue(undefined);
  // Clear localStorage between tests so collapse state doesn't leak.
  window.localStorage.clear();
});

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('ProjectNode', () => {
  it('renders project name with monorepo + 0 tasks meta', async () => {
    wrap(<ProjectNode project={monorepoProject} onError={() => {}} />);
    expect(await screen.findByText('gcb-financeiro')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/monorepo · 0 tasks ativas/)).toBeInTheDocument();
    });
  });

  it('renders sub-repos label and active task count', async () => {
    vi.mocked(api.listTasks).mockResolvedValue([
      task('t1', 'in_progress', 'Add OAuth'),
    ]);
    vi.mocked(api.listWorktrees).mockResolvedValue([
      { ...wt('w1', 't1', 'add-oauth'), repository_id: 'r2', repository_name: 'backend' },
      { ...wt('w2', 't1', 'add-oauth'), repository_id: 'r3', repository_name: 'frontend' },
    ]);
    wrap(<ProjectNode project={multiRepoProject} onError={() => {}} />);
    await screen.findByText('gcb-hub');
    await waitFor(() => {
      expect(screen.getByText(/2 sub-repos · 1 task ativa/)).toBeInTheDocument();
    });
  });

  it('hides children when collapsed and persists state in localStorage', async () => {
    vi.mocked(api.listTasks).mockResolvedValue([task('t1', 'in_progress', 'X')]);
    vi.mocked(api.listWorktrees).mockResolvedValue([wt('w1', 't1', 'b1')]);
    wrap(<ProjectNode project={monorepoProject} onError={() => {}} />);
    await screen.findByText('"X"');
    fireEvent.click(screen.getByLabelText('collapse-gcb-financeiro'));
    expect(screen.queryByText('"X"')).toBeNull();
    expect(window.localStorage.getItem('jarvis.proj.p1.collapsed')).toBe('true');
  });

  it('reads collapsed state from localStorage on mount', async () => {
    window.localStorage.setItem('jarvis.proj.p1.collapsed', 'true');
    vi.mocked(api.listTasks).mockResolvedValue([task('t1', 'in_progress', 'X')]);
    vi.mocked(api.listWorktrees).mockResolvedValue([wt('w1', 't1', 'b1')]);
    wrap(<ProjectNode project={monorepoProject} onError={() => {}} />);
    await screen.findByText('gcb-financeiro');
    expect(screen.queryByText('"X"')).toBeNull();
    expect(screen.getByLabelText('expand-gcb-financeiro')).toBeInTheDocument();
  });

  it('filters out tasks not in_progress/review or without worktrees', async () => {
    vi.mocked(api.listTasks).mockResolvedValue([
      task('t1', 'idea', 'Idea'),
      task('t2', 'ready', 'Ready'),
      task('t3', 'done', 'Done'),
      task('t4', 'discarded', 'Discarded'),
      task('t5', 'in_progress', 'No-WT'), // no worktrees
      task('t6', 'in_progress', 'With-WT'),
      task('t7', 'review', 'Reviewing'),
    ]);
    vi.mocked(api.listWorktrees).mockResolvedValue([
      wt('w6', 't6', 'b6'),
      wt('w7', 't7', 'b7'),
    ]);
    wrap(<ProjectNode project={monorepoProject} onError={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText('"With-WT"')).toBeInTheDocument();
    });
    expect(screen.getByText('"Reviewing"')).toBeInTheDocument();
    expect(screen.queryByText('"Idea"')).toBeNull();
    expect(screen.queryByText('"Ready"')).toBeNull();
    expect(screen.queryByText('"Done"')).toBeNull();
    expect(screen.queryByText('"Discarded"')).toBeNull();
    expect(screen.queryByText('"No-WT"')).toBeNull();
  });

  it('renders OrphansGroup only when there are orphans', async () => {
    vi.mocked(api.listTasks).mockResolvedValue([]);
    vi.mocked(api.listWorktrees).mockResolvedValue([wt('w1', null, 'experiment')]);
    wrap(<ProjectNode project={monorepoProject} onError={() => {}} />);
    expect(await screen.findByText('órfãs (1)')).toBeInTheDocument();
    expect(screen.getByText('experiment')).toBeInTheDocument();
  });

  it('does not render OrphansGroup when there are no orphans', async () => {
    vi.mocked(api.listTasks).mockResolvedValue([task('t1', 'in_progress', 'X')]);
    vi.mocked(api.listWorktrees).mockResolvedValue([wt('w1', 't1', 'b1')]);
    wrap(<ProjectNode project={monorepoProject} onError={() => {}} />);
    await screen.findByText('"X"');
    expect(screen.queryByText(/órfãs/)).toBeNull();
  });

  it('calls api.deleteProject when Excluir clicked', async () => {
    wrap(<ProjectNode project={monorepoProject} onError={() => {}} />);
    await screen.findByText('gcb-financeiro');
    fireEvent.click(screen.getByLabelText('delete-gcb-financeiro'));
    await waitFor(() => {
      expect(api.deleteProject).toHaveBeenCalledWith('p1');
    });
  });

  it('calls onError with translated message when deleteProject fails', async () => {
    vi.mocked(api.deleteProject).mockRejectedValueOnce(
      new Error('project has 2 task(s); discard them before deleting'),
    );
    const onError = vi.fn();
    wrap(<ProjectNode project={monorepoProject} onError={onError} />);
    await screen.findByText('gcb-financeiro');
    fireEvent.click(screen.getByLabelText('delete-gcb-financeiro'));
    await waitFor(() => {
      expect(onError).toHaveBeenCalled();
    });
    expect(onError.mock.calls[0]?.[0]).toMatch(/Descarte as tasks/i);
  });
});
