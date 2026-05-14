import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TaskCard } from './TaskCard';
import { DndContext } from '@dnd-kit/core';

// In_progress/review states embed <RunStatus /> which queries the run.
// TaskCard also calls useCatalog for badge tooltips. Stub both endpoints.
vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual('../../lib/api');
  return {
    ...actual,
    api: {
      getActiveRun: vi.fn().mockRejectedValue(new Error('HTTP 404')),
      getCatalog: vi.fn(),
    },
  };
});

// Session controls pull sandbox availability + the task's sessions. Mock the
// hooks directly so each test controls those two inputs in isolation.
vi.mock('../../hooks/useSandboxHealth', () => ({ useSandboxHealth: vi.fn() }));
vi.mock('../../hooks/useSessions', () => ({ useSessions: vi.fn() }));

import { api, type Task, type Project, type Catalog, type Session } from '../../lib/api';
import { useSandboxHealth } from '../../hooks/useSandboxHealth';
import { useSessions } from '../../hooks/useSessions';

const emptyCatalog: Catalog = {
  version: '1',
  fallback_permission_profile: 'yolo',
  permission_profiles: [],
  templates: [],
};

function makeSession(over: Partial<Session> = {}): Session {
  return {
    id: 'sess-1', task_id: 't1', status: 'executing', pid: 100,
    cwd: '/tmp/wt', last_hook_at: null,
    started_at: '2026-01-01T00:00:00Z', ended_at: null,
    ...over,
  };
}

beforeEach(() => {
  vi.mocked(api.getCatalog).mockResolvedValue(emptyCatalog);
  vi.mocked(useSandboxHealth).mockReturnValue({
    data: { sandbox_available: true, sandbox_reason: '' },
  } as unknown as ReturnType<typeof useSandboxHealth>);
  vi.mocked(useSessions).mockReturnValue({
    data: [],
  } as unknown as ReturnType<typeof useSessions>);
});

const baseTask: Task = {
  id: 't1', project_id: 'p1', title: 'Adicionar dark mode',
  description: '', state: 'idea',
  template: null, permission_profile: null, branch: null,
  created_at: '2026', updated_at: '2026', active_session_id: null,
};

const projects = new Map<string, Project>([
  ['p1', { id: 'p1', name: 'projA', path: '/p', created_at: '2026', repositories: [] }],
]);

function wrap(node: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <DndContext>{node}</DndContext>
    </QueryClientProvider>,
  );
}

describe('TaskCard', () => {
  it('renders title and project chip', () => {
    wrap(<TaskCard task={baseTask} projects={projects} />);
    expect(screen.getByText('Adicionar dark mode')).toBeInTheDocument();
    expect(screen.getByText('● projA')).toBeInTheDocument();
  });
  it('renders sub-tag idea on idea state', () => {
    wrap(<TaskCard task={baseTask} projects={projects} />);
    expect(screen.getByText('idea')).toBeInTheDocument();
  });
  it('renders ready sub-tag', () => {
    wrap(<TaskCard task={{ ...baseTask, state: 'ready' }} projects={projects} />);
    expect(screen.getByText('ready')).toBeInTheDocument();
  });
  it('does not render sub-tag on in_progress state', () => {
    wrap(<TaskCard task={{ ...baseTask, state: 'in_progress' }} projects={projects} />);
    expect(screen.queryByText('idea')).toBeNull();
    expect(screen.queryByText('ready')).toBeNull();
  });

  it('renders template and permission_profile badges when set', () => {
    const t: Task = { ...baseTask, template: 'bugfix', permission_profile: 'yolo' };
    wrap(<TaskCard task={t} projects={projects} />);
    const templateBadge = screen.getByText('bugfix');
    expect(templateBadge).toHaveAttribute('data-template-name', 'bugfix');
    const profileBadge = screen.getByText('yolo');
    expect(profileBadge).toHaveAttribute('data-permission-profile', 'yolo');
  });

  it('omits badges when template/permission_profile are null', () => {
    wrap(<TaskCard task={baseTask} projects={projects} />);
    expect(screen.queryByTestId('template-badge')).toBeNull();
    expect(screen.queryByTestId('profile-badge')).toBeNull();
  });

  it.each([
    ['yolo', 'yellow'],
    ['default', 'gray'],
    ['read-only', 'green'],
  ])('applies known color for profile %s → %s', (profile, color) => {
    const t: Task = { ...baseTask, template: 'frontend', permission_profile: profile };
    wrap(<TaskCard task={t} projects={projects} />);
    const badge = screen.getByText(profile);
    expect(badge.getAttribute('data-profile-color')).toBe(color);
  });

  it('applies gray color fallback for unknown profiles', () => {
    const t: Task = { ...baseTask, template: 'custom', permission_profile: 'paranoid' };
    wrap(<TaskCard task={t} projects={projects} />);
    const badge = screen.getByText('paranoid');
    expect(badge.getAttribute('data-profile-color')).toBe('gray');
  });

  it('shows catalog description as template/profile badge tooltip', async () => {
    vi.mocked(api.getCatalog).mockResolvedValue({
      version: '1',
      fallback_permission_profile: 'yolo',
      permission_profiles: [
        { name: 'yolo', description: 'Skip todos os prompts', claude_args: [] },
      ],
      templates: [
        {
          name: 'bugfix',
          description: 'Correção de defeito',
          default_permission_profile: 'yolo',
          branch_prefix: 'fix/',
        },
      ],
    });
    const t: Task = { ...baseTask, template: 'bugfix', permission_profile: 'yolo' };
    wrap(<TaskCard task={t} projects={projects} />);
    await waitFor(() => {
      expect(screen.getByTestId('template-badge')).toHaveAttribute(
        'title',
        'Correção de defeito',
      );
    });
    expect(screen.getByTestId('profile-badge')).toHaveAttribute(
      'title',
      'Skip todos os prompts',
    );
  });

  it('falls back to name when catalog lookup misses', async () => {
    vi.mocked(api.getCatalog).mockResolvedValue({
      version: '1',
      fallback_permission_profile: 'yolo',
      permission_profiles: [],
      templates: [],
    });
    const t: Task = { ...baseTask, template: 'custom', permission_profile: 'paranoid' };
    wrap(<TaskCard task={t} projects={projects} />);
    await waitFor(() => {
      expect(screen.getByTestId('template-badge')).toHaveAttribute('title', 'custom');
    });
    expect(screen.getByTestId('profile-badge')).toHaveAttribute(
      'title',
      'Perfil: paranoid',
    );
  });

  describe('data-card-state', () => {
    it('sets data-card-state=idle for a default idea task', () => {
      const { container } = wrap(<TaskCard task={baseTask} projects={projects} />);
      expect(container.firstChild).toHaveAttribute('data-card-state', 'idle');
    });

    it('sets data-card-state=running when task state is in_progress', () => {
      const t: Task = { ...baseTask, state: 'in_progress' };
      const { container } = wrap(<TaskCard task={t} projects={projects} />);
      expect(container.firstChild).toHaveAttribute('data-card-state', 'running');
    });

    it('sets data-card-state=done when task state is done', () => {
      const t: Task = { ...baseTask, state: 'done' };
      const { container } = wrap(<TaskCard task={t} projects={projects} />);
      expect(container.firstChild).toHaveAttribute('data-card-state', 'done');
    });

    it('sets data-card-state=error when task state is error', () => {
      const t: Task = { ...baseTask, state: 'error' };
      const { container } = wrap(<TaskCard task={t} projects={projects} />);
      expect(container.firstChild).toHaveAttribute('data-card-state', 'error');
    });
  });

  describe('session controls', () => {
    it('disables the start button when the sandbox is unavailable', () => {
      vi.mocked(useSandboxHealth).mockReturnValue({
        data: { sandbox_available: false, sandbox_reason: 'ai-jail não está no PATH' },
      } as unknown as ReturnType<typeof useSandboxHealth>);
      wrap(<TaskCard task={baseTask} projects={projects} />);
      const btn = screen.getByTestId('task-session-start');
      expect(btn).toBeDisabled();
      expect(btn).toHaveAttribute('title', 'ai-jail não está no PATH');
    });

    it('enables the start button when the sandbox is available and no session is active', () => {
      wrap(<TaskCard task={baseTask} projects={projects} />);
      const btn = screen.getByTestId('task-session-start');
      expect(btn).toBeEnabled();
      expect(btn).toHaveAttribute('title', '');
    });

    it('shows the status chip instead of the start button when a session is active', () => {
      vi.mocked(useSessions).mockReturnValue({
        data: [makeSession({ status: 'awaiting_response' })],
      } as unknown as ReturnType<typeof useSessions>);
      wrap(<TaskCard task={baseTask} projects={projects} />);
      expect(screen.getByTestId('task-session-open')).toBeInTheDocument();
      expect(screen.getByTestId('session-status-chip')).toBeInTheDocument();
      expect(screen.queryByTestId('task-session-start')).toBeNull();
    });
  });
});
