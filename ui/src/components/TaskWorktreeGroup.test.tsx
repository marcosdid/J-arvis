import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TaskWorktreeGroup } from './TaskWorktreeGroup';
import type { Task, Worktree } from '../lib/api';

const baseTask: Task = {
  id: 't1',
  project_id: 'p1',
  title: 'Refactor login',
  description: '',
  state: 'in_progress',
  template: null,
  permission_profile: null,
  branch: null,
  created_at: '',
  updated_at: '',
  active_session_id: null,
};

const wt = (id: string, repo: string, branch: string): Worktree => ({
  id,
  repository_id: `r-${repo}`,
  repository_name: repo,
  task_id: 't1',
  path: `/p/${repo}/${branch}`,
  branch,
  is_orphan: false,
});

describe('TaskWorktreeGroup', () => {
  it('renders task title and state icon for in_progress', () => {
    render(<TaskWorktreeGroup task={baseTask} worktrees={[wt('w1', 'backend', 'refactor-login')]} />);
    expect(screen.getByText('"Refactor login"')).toBeInTheDocument();
    expect(screen.getByText(/●/)).toBeInTheDocument();
    expect(screen.getByText(/in-progress/)).toBeInTheDocument();
  });

  it('renders state icon · for review', () => {
    render(<TaskWorktreeGroup task={{ ...baseTask, state: 'review' }} worktrees={[wt('w1', 'backend', 'b')]} />);
    expect(screen.getByText(/review/)).toBeInTheDocument();
  });

  it('passes showRepoName=false when single worktree (monorepo)', () => {
    render(<TaskWorktreeGroup task={baseTask} worktrees={[wt('w1', 'backend', 'b1')]} />);
    expect(screen.queryByText('backend')).toBeNull();
    expect(screen.getByText('b1')).toBeInTheDocument();
  });

  it('passes showRepoName=true when multiple worktrees (multi-repo)', () => {
    render(
      <TaskWorktreeGroup
        task={baseTask}
        worktrees={[wt('w1', 'backend', 'b'), wt('w2', 'frontend', 'b')]}
      />,
    );
    expect(screen.getByText('backend')).toBeInTheDocument();
    expect(screen.getByText('frontend')).toBeInTheDocument();
  });

  it('toggles open/closed when header button clicked', () => {
    render(<TaskWorktreeGroup task={baseTask} worktrees={[wt('w1', 'backend', 'b1')]} />);
    expect(screen.getByText('b1')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(`collapse-task-${baseTask.id}`));
    expect(screen.queryByText('b1')).toBeNull();
    fireEvent.click(screen.getByLabelText(`expand-task-${baseTask.id}`));
    expect(screen.getByText('b1')).toBeInTheDocument();
  });
});
