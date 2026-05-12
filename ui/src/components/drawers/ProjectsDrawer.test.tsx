import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { ProjectsDrawer } from './ProjectsDrawer';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual('../../lib/api');
  return {
    ...actual,
    api: {
      listProjects: vi.fn(),
      createProject: vi.fn(),
      deleteProject: vi.fn(),
      listWorktrees: vi.fn(),
      listTasks: vi.fn(),
      deleteWorktree: vi.fn(),
    },
  };
});

import { api } from '../../lib/api';

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listProjects).mockResolvedValue([
    {
      id: 'p1',
      name: 'projA',
      path: '/p',
      created_at: '',
      repositories: [{ id: 'r1', name: 'projA', sub_path: '.' }],
    },
  ]);
  vi.mocked(api.listWorktrees).mockResolvedValue([]);
  vi.mocked(api.listTasks).mockResolvedValue([]);
  vi.mocked(api.deleteProject).mockResolvedValue(undefined);
  vi.mocked(api.createProject).mockResolvedValue({} as never);
  window.localStorage.clear();
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

  it('renders the projects header and project name when open', async () => {
    wrap(<ProjectsDrawer open={true} onClose={() => {}} />);
    expect(screen.getByText('Projetos & Worktrees')).toBeInTheDocument();
    expect(await screen.findByText('projA')).toBeInTheDocument();
  });

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn();
    wrap(<ProjectsDrawer open={true} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText(/close-drawer/i));
    expect(onClose).toHaveBeenCalled();
  });

  it('renders create-project form fields', () => {
    wrap(<ProjectsDrawer open={true} onClose={() => {}} />);
    expect(screen.getByLabelText('project-name')).toBeInTheDocument();
    expect(screen.getByLabelText('project-path')).toBeInTheDocument();
  });

  it('submits create-project form and clears inputs on success', async () => {
    wrap(<ProjectsDrawer open={true} onClose={() => {}} />);
    const name = screen.getByLabelText('project-name') as HTMLInputElement;
    const path = screen.getByLabelText('project-path') as HTMLInputElement;
    fireEvent.change(name, { target: { value: 'newP' } });
    fireEvent.change(path, { target: { value: '/np' } });
    fireEvent.click(screen.getByRole('button', { name: /adicionar projeto/i }));
    await waitFor(() => {
      expect(api.createProject).toHaveBeenCalledWith('newP', '/np');
    });
    await waitFor(() => expect(name.value).toBe(''));
    expect(path.value).toBe('');
  });

  it('shows pt-BR toast bubbled from ProjectNode when delete fails', async () => {
    vi.mocked(api.deleteProject).mockRejectedValueOnce(
      new Error('project has 2 task(s); discard them before deleting'),
    );
    wrap(<ProjectsDrawer open={true} onClose={() => {}} />);
    await screen.findByText('projA');
    fireEvent.click(screen.getByLabelText('delete-projA'));
    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toMatch(/Descarte as tasks/i);
    });
  });

  it('clicking the toast dismisses it', async () => {
    vi.mocked(api.deleteProject).mockRejectedValueOnce(new Error('boom'));
    wrap(<ProjectsDrawer open={true} onClose={() => {}} />);
    await screen.findByText('projA');
    fireEvent.click(screen.getByLabelText('delete-projA'));
    const toast = await screen.findByRole('alert');
    fireEvent.click(toast);
    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
  });
});
