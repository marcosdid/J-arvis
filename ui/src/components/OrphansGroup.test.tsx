import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { OrphansGroup } from './OrphansGroup';
import type { Project, Worktree } from '../lib/api';

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api');
  return {
    ...actual,
    api: {
      deleteWorktree: vi.fn(),
    },
  };
});

import { api } from '../lib/api';

const project: Project = {
  id: 'p1',
  name: 'projA',
  path: '/p',
  created_at: '',
  repositories: [{ id: 'r1', name: 'backend', sub_path: '.' }],
};

const orphan: Worktree = {
  id: 'w1',
  repository_id: 'r1',
  repository_name: 'backend',
  task_id: null,
  path: '/p/backend/experiment',
  branch: 'experiment',
  is_orphan: true,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.deleteWorktree).mockResolvedValue(undefined);
});

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('OrphansGroup', () => {
  it('renders orphan count and rows with ✕ button', () => {
    wrap(<OrphansGroup project={project} worktrees={[orphan]} onError={() => {}} />);
    expect(screen.getByText('órfãs (1)')).toBeInTheDocument();
    expect(screen.getByText('experiment')).toBeInTheDocument();
    expect(screen.getByLabelText('remove-worktree-w1')).toBeInTheDocument();
  });

  it('toggles open/closed via collapse button', () => {
    wrap(<OrphansGroup project={project} worktrees={[orphan]} onError={() => {}} />);
    expect(screen.getByText('experiment')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('collapse-orphans'));
    expect(screen.queryByText('experiment')).toBeNull();
    fireEvent.click(screen.getByLabelText('expand-orphans'));
    expect(screen.getByText('experiment')).toBeInTheDocument();
  });

  it('calls api.deleteWorktree when ✕ clicked', async () => {
    wrap(<OrphansGroup project={project} worktrees={[orphan]} onError={() => {}} />);
    fireEvent.click(screen.getByLabelText('remove-worktree-w1'));
    await waitFor(() => {
      expect(api.deleteWorktree).toHaveBeenCalledWith('w1');
    });
  });

  it('calls onError with translated message when deleteWorktree fails', async () => {
    vi.mocked(api.deleteWorktree).mockRejectedValueOnce(
      new Error('worktree has active session'),
    );
    const onError = vi.fn();
    wrap(<OrphansGroup project={project} worktrees={[orphan]} onError={onError} />);
    fireEvent.click(screen.getByLabelText('remove-worktree-w1'));
    await waitFor(() => {
      expect(onError).toHaveBeenCalled();
    });
    const msg = onError.mock.calls[0]?.[0];
    expect(typeof msg).toBe('string');
  });

  it('passes showRepoName=true when project has multiple repositories', () => {
    const multi: Project = {
      ...project,
      repositories: [
        { id: 'r1', name: 'backend', sub_path: 'backend' },
        { id: 'r2', name: 'frontend', sub_path: 'frontend' },
      ],
    };
    wrap(<OrphansGroup project={multi} worktrees={[orphan]} onError={() => {}} />);
    expect(screen.getByText('backend')).toBeInTheDocument();
  });
});
