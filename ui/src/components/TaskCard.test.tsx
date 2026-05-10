import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TaskCard } from './TaskCard';
import type { Task, Project } from '../lib/api';
import { DndContext } from '@dnd-kit/core';

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
  return render(<DndContext>{node}</DndContext>);
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
