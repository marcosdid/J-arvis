import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { WorktreeRow } from './WorktreeRow';
import type { Worktree } from '../lib/api';

const baseWt: Worktree = {
  id: 'w1',
  repository_id: 'r1',
  repository_name: 'backend',
  task_id: 't1',
  path: '/abs/path/backend/refactor-login',
  branch: 'refactor-login',
  is_orphan: false,
};

describe('WorktreeRow', () => {
  it('renders branch label only when showRepoName is false (monorepo)', () => {
    render(<WorktreeRow wt={baseWt} showRepoName={false} />);
    expect(screen.getByText('refactor-login')).toBeInTheDocument();
    expect(screen.queryByText('backend')).toBeNull();
  });

  it('renders <repo> / <branch> when showRepoName is true (multi-repo)', () => {
    render(<WorktreeRow wt={baseWt} showRepoName={true} />);
    expect(screen.getByText('backend')).toBeInTheDocument();
    expect(screen.getByText('refactor-login')).toBeInTheDocument();
    expect(screen.getByText('/')).toBeInTheDocument();
  });

  it('renders (detached) when branch is null', () => {
    render(<WorktreeRow wt={{ ...baseWt, branch: null }} showRepoName={false} />);
    expect(screen.getByText('(detached)')).toBeInTheDocument();
  });

  it('exposes path as title attribute (tooltip)', () => {
    const { container } = render(<WorktreeRow wt={baseWt} showRepoName={false} />);
    const row = container.querySelector('.wt-row') as HTMLElement;
    expect(row.title).toBe('/abs/path/backend/refactor-login');
  });

  it('does not render remove button when onRemove is omitted', () => {
    render(<WorktreeRow wt={baseWt} showRepoName={false} />);
    expect(screen.queryByLabelText(/remove-worktree/i)).toBeNull();
  });

  it('renders ✕ button and calls onRemove with id when clicked', () => {
    const onRemove = vi.fn();
    render(<WorktreeRow wt={baseWt} showRepoName={false} onRemove={onRemove} />);
    fireEvent.click(screen.getByLabelText('remove-worktree-w1'));
    expect(onRemove).toHaveBeenCalledWith('w1');
  });
});
