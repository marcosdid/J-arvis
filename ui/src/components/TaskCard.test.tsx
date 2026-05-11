import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TaskCard } from './TaskCard';
import type { Task, Project } from '../lib/api';
import { DndContext } from '@dnd-kit/core';

// In_progress/review states embed <RunStatus /> which queries the run.
// Stub api so the hook resolves cleanly to "no active run".
vi.mock('../lib/api', () => ({
  api: { getActiveRun: vi.fn().mockRejectedValue(new Error('HTTP 404')) },
}));

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
});
