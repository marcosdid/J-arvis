import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, type Project, type Worktree } from '../lib/api';
import { translateError } from '../lib/errorMessages';
import { queryKeys } from '../lib/query-keys';
import { WorktreeRow } from './WorktreeRow';

type Props = {
  project: Project;
  worktrees: Worktree[];
  onError: (msg: string) => void;
};

export function OrphansGroup({ project, worktrees, onError }: Props) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(true);

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteWorktree(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: queryKeys.worktrees(project.id) }),
    onError: (err: unknown) => {
      const msg = (err as Error).message ?? String(err);
      onError(translateError(msg));
    },
  });

  return (
    <div className="orphans-group">
      <header>
        <button
          type="button"
          aria-label={open ? 'collapse-orphans' : 'expand-orphans'}
          onClick={() => setOpen(!open)}
        >
          {open ? '▼' : '▶'}
        </button>
        <span className="orphans-label">órfãs ({worktrees.length})</span>
      </header>
      {open && worktrees.map((w) => (
        <WorktreeRow
          key={w.id}
          wt={w}
          showRepoName={project.repositories.length > 1}
          onRemove={(id) => remove.mutate(id)}
        />
      ))}
    </div>
  );
}
