import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { ProjectsDrawer } from './ProjectsDrawer';

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api');
  return {
    ...actual,
    api: {
      listProjects: vi.fn(),
      createProject: vi.fn(),
      deleteProject: vi.fn(),
      listWorktrees: vi.fn(),
      createWorktree: vi.fn(),
      deleteWorktree: vi.fn(),
      startSession: vi.fn(),
    },
  };
});

import { api } from '../lib/api';

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listProjects).mockResolvedValue([
    { id: 'p1', name: 'projA', path: '/p', created_at: '' },
  ]);
  vi.mocked(api.listWorktrees).mockResolvedValue([
    { id: 'w1', project_id: 'p1', branch: 'main', path: '/p' },
  ]);
});

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('ProjectsDrawer', () => {
  it('renders nothing when closed', () => {
    wrap(<ProjectsDrawer open={false} onClose={() => {}} />);
    expect(screen.queryByText('projA')).toBeNull();
  });

  it('renders projects when open', async () => {
    wrap(<ProjectsDrawer open={true} onClose={() => {}} />);
    expect(await screen.findByText('projA')).toBeInTheDocument();
  });

  it('renders worktrees inline per project', async () => {
    wrap(<ProjectsDrawer open={true} onClose={() => {}} />);
    await screen.findByText('projA');
    expect(await screen.findByText('main')).toBeInTheDocument();
  });

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn();
    wrap(<ProjectsDrawer open={true} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText(/close-drawer/i));
    expect(onClose).toHaveBeenCalled();
  });

  it('shows pt-BR toast when delete-project returns 409', async () => {
    vi.mocked(api.deleteProject).mockRejectedValueOnce(
      new Error('project has 2 task(s); discard them before deleting')
    );
    wrap(<ProjectsDrawer open={true} onClose={() => {}} />);
    await screen.findByText('projA');
    fireEvent.click(screen.getByLabelText(/delete-projA/i));
    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toMatch(/Descarte as tasks/i);
    });
  });

  it('quick session button calls api.startSession with worktree id', async () => {
    vi.mocked(api.startSession).mockResolvedValueOnce({} as never);
    wrap(<ProjectsDrawer open={true} onClose={() => {}} />);
    await screen.findByText('main');
    const btn = screen.getByLabelText(/quick-main/i);
    fireEvent.click(btn);
    await waitFor(() => {
      expect(api.startSession).toHaveBeenCalledWith('w1');
    });
  });
});
