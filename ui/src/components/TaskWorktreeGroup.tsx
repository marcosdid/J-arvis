import { useState } from 'react';
import type { Task, Worktree } from '../lib/api';
import { WorktreeRow } from './WorktreeRow';

type Props = {
  task: Task;
  worktrees: Worktree[];
};

const STATE_ICON: Record<string, string> = {
  in_progress: '●',
  review: '·',
};

export function TaskWorktreeGroup({ task, worktrees }: Props) {
  const [open, setOpen] = useState(true);
  const showRepoName = worktrees.length > 1;

  return (
    <div className="task-group" data-task-id={task.id}>
      <header>
        <button
          type="button"
          aria-label={open ? `collapse-task-${task.id}` : `expand-task-${task.id}`}
          onClick={() => setOpen(!open)}
        >
          {open ? '▼' : '▶'}
        </button>
        <span className="task-title">"{task.title}"</span>
        <span className="task-state" data-state={task.state}>
          {STATE_ICON[task.state] ?? '·'} {task.state.replace('_', '-')}
        </span>
      </header>
      {open && worktrees.map((w) => (
        <WorktreeRow key={w.id} wt={w} showRepoName={showRepoName} />
      ))}
    </div>
  );
}
