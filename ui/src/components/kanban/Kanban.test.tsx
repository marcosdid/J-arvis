import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { Kanban } from './Kanban';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual('../../lib/api');
  return {
    ...actual,
    api: {
      listTasks: vi.fn(),
      patchTask: vi.fn(),
      listProjects: vi.fn(),
    },
  };
});

import { api } from '../../lib/api';

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listTasks).mockResolvedValue([
    {
      id: 't1', project_id: 'p1', title: 'A', state: 'idea',
      description: '', template: null, permission_profile: null, branch: null,
      created_at: '', updated_at: '', active_session_id: null,
    },
    {
      id: 't2', project_id: 'p1', title: 'B', state: 'in_progress',
      description: '', template: null, permission_profile: null, branch: null,
      created_at: '', updated_at: '', active_session_id: 's1',
    },
  ]);
  vi.mocked(api.listProjects).mockResolvedValue([
    { id: 'p1', name: 'projA', path: '/p', created_at: '', repositories: [] },
  ]);
  vi.mocked(api.patchTask).mockResolvedValue({} as never);
});

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('Kanban', () => {
  it('renders 5 columns', async () => {
    wrap(<Kanban filters={[]} />);
    expect(await screen.findByText('Backlog')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getByText('Review')).toBeInTheDocument();
    expect(screen.getByText('Done')).toBeInTheDocument();
    expect(screen.getByText('Discarded')).toBeInTheDocument();
  });

  it('places idea task in Backlog and in_progress in In Progress', async () => {
    wrap(<Kanban filters={[]} />);
    await screen.findByText('A');
    const backlog = screen.getByTestId('column-Backlog');
    const inprog = screen.getByTestId('column-In Progress');
    expect(backlog).toContainElement(screen.getByText('A'));
    expect(inprog).toContainElement(screen.getByText('B'));
  });

  it('does NOT call patchTask when transition is invalid (snap-back)', async () => {
    wrap(<Kanban filters={[]} />);
    await screen.findByText('A');
    // idea → Done is invalid
    fireEvent(window, new CustomEvent('test:dragEnd', {
      detail: { taskId: 't1', column: 'Done' },
    }));
    // Confirm error toast appears
    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toMatch(/Transição/i);
    });
    expect(api.patchTask).not.toHaveBeenCalled();
  });

  it('calls patchTask when transition is valid', async () => {
    wrap(<Kanban filters={[]} />);
    await screen.findByText('A');
    // idea → Backlog resolves to 'ready', valid transition
    fireEvent(window, new CustomEvent('test:dragEnd', {
      detail: { taskId: 't1', column: 'Backlog' },
    }));
    await waitFor(() => {
      expect(api.patchTask).toHaveBeenCalledWith('t1', { state: 'ready' });
    });
  });

  it('intra-column reorder is no-op (target state same as current)', async () => {
    vi.mocked(api.listTasks).mockResolvedValue([
      {
        id: 't3', project_id: 'p1', title: 'C', state: 'ready',
        description: '', template: null, permission_profile: null, branch: null,
        created_at: '', updated_at: '', active_session_id: null,
      },
    ]);
    wrap(<Kanban filters={[]} />);
    await screen.findByText('C');
    fireEvent(window, new CustomEvent('test:dragEnd', {
      detail: { taskId: 't3', column: 'Backlog' },
    }));
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(api.patchTask).not.toHaveBeenCalled();
  });
});
