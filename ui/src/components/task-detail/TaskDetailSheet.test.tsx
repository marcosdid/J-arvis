import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { TaskDetailSheet } from './TaskDetailSheet';

vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual('../../lib/api');
  return {
    ...actual,
    api: {
      getTask: vi.fn(),
      patchTask: vi.fn(),
      startTaskSession: vi.fn(),
      listWorktrees: vi.fn(),
      getActiveRun: vi.fn(),
      startRun: vi.fn(),
      stopRun: vi.fn(),
      bootstrapManifest: vi.fn(),
    },
  };
});
vi.mock('../../lib/runSseClient', () => ({
  createLogsSse: vi.fn(() => ({ close: vi.fn() })),
}));

import { api } from '../../lib/api';

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getTask).mockResolvedValue({
    id: 't1', project_id: 'p1', title: 'My Task', description: 'Desc',
    state: 'ready', template: null, permission_profile: null, branch: null,
    created_at: '', updated_at: '', active_session_id: null,
  });
  vi.mocked(api.patchTask).mockResolvedValue({} as never);
  vi.mocked(api.startTaskSession).mockResolvedValue({} as never);
  vi.mocked(api.listWorktrees).mockResolvedValue([]);
  vi.mocked(api.getActiveRun).mockRejectedValue(new Error('HTTP 404: no active run'));
});

function wrap(taskId: string | null = 't1', onClose = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TaskDetailSheet taskId={taskId} onClose={onClose} />
    </QueryClientProvider>,
  );
}

describe('TaskDetailSheet', () => {
  it('renders nothing visible when taskId is null', () => {
    wrap(null);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders sheet with task title when open', async () => {
    wrap('t1');
    expect(await screen.findByText('My Task')).toBeDefined();
  });

  it('renders 4 tab triggers', async () => {
    wrap('t1');
    await screen.findByText('My Task');
    expect(screen.getByRole('tab', { name: /overview/i })).toBeDefined();
    expect(screen.getByRole('tab', { name: /sessions/i })).toBeDefined();
    expect(screen.getByRole('tab', { name: /run/i })).toBeDefined();
    expect(screen.getByRole('tab', { name: /logs/i })).toBeDefined();
  });

  it('shows OverviewTab content by default', async () => {
    wrap('t1');
    // Overview tab renders the title input
    const input = await screen.findByDisplayValue('My Task');
    expect(input).toBeDefined();
  });

  it('calls onClose when sheet is closed', async () => {
    const onClose = vi.fn();
    wrap('t1', onClose);
    await screen.findByText('My Task');
    // Click the close button rendered by shadcn SheetContent
    const closeBtn = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeBtn);
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  // Radix Tabs uses onMouseDown for tab selection (not onClick)
  it('switches to sessions tab and shows placeholder', async () => {
    wrap('t1');
    await screen.findByText('My Task');
    const sessionsTab = screen.getByRole('tab', { name: /sessions/i });
    fireEvent.mouseDown(sessionsTab);
    await waitFor(() => {
      expect(screen.getByText(/sessions list coming/i)).toBeDefined();
    });
  });

  it('switches to logs tab and shows placeholder', async () => {
    wrap('t1');
    await screen.findByText('My Task');
    const logsTab = screen.getByRole('tab', { name: /logs/i });
    fireEvent.mouseDown(logsTab);
    await waitFor(() => {
      expect(screen.getByText(/logs streaming coming soon/i)).toBeDefined();
    });
  });
});
