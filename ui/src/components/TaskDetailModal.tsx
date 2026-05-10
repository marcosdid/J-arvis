import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { isValidTransition } from '../lib/transitions';
import { translateError } from '../lib/errorMessages';
import { usePatchTask, useStartTaskSession } from '../hooks/useTaskMutations';

const ALL_STATES = ['idea', 'ready', 'in_progress', 'review', 'done', 'discarded'];

type Props = { taskId: string; onClose: () => void };

export function TaskDetailModal({ taskId, onClose }: Props) {
  const task = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => api.getTask(taskId),
  });
  const worktrees = useQuery({
    queryKey: ['worktrees', task.data?.project_id],
    queryFn: () => api.listWorktrees(task.data!.project_id),
    enabled: !!task.data,
  });
  const patch = usePatchTask();
  const start = useStartTaskSession();

  const [titleDraft, setTitleDraft] = useState('');
  const [descDraft, setDescDraft] = useState('');
  const [selectedWorktree, setSelectedWorktree] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (task.data) {
      setTitleDraft(task.data.title);
      setDescDraft(task.data.description);
    }
  }, [task.data?.id, task.data?.title, task.data?.description]);

  // Debounced PATCH for title/description
  useEffect(() => {
    if (!task.data) return;
    if (titleDraft === task.data.title && descDraft === task.data.description) return;
    if (!titleDraft.trim()) return;
    const tid = setTimeout(() => {
      const update: Record<string, string> = {};
      if (titleDraft !== task.data!.title) update.title = titleDraft;
      if (descDraft !== task.data!.description) update.description = descDraft;
      if (Object.keys(update).length === 0) return;
      patch.mutate({ id: taskId, patch: update });
    }, 500);
    return () => clearTimeout(tid);
    // deps limited to draft values — task.data read via closure, not as a trigger
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [titleDraft, descDraft]);

  if (!task.data) return null;
  const t = task.data;

  const moveTargets = ALL_STATES.filter(
    (s) => s !== t.state && isValidTransition(t.state, s),
  );

  const isTerminal = t.state === 'done' || t.state === 'discarded';

  return (
    <div role="dialog" className="modal" aria-label={t.title}>
      <button onClick={onClose} aria-label="close">✕</button>
      <input
        aria-label="title"
        value={titleDraft}
        onChange={(e) => setTitleDraft(e.target.value)}
      />
      <textarea
        aria-label="description"
        value={descDraft}
        onChange={(e) => setDescDraft(e.target.value)}
      />
      <label>
        Move to:
        <select
          aria-label="move to"
          value=""
          onChange={(e) => {
            if (!e.target.value) return;
            patch.mutate({ id: taskId, patch: { state: e.target.value } });
          }}
        >
          <option value="">—</option>
          {moveTargets.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>

      <h4>Sessions</h4>

      <label>
        Worktree:
        <select
          aria-label="worktree"
          value={selectedWorktree}
          onChange={(e) => setSelectedWorktree(e.target.value)}
        >
          <option value="">—</option>
          {(worktrees.data ?? []).map((w) => (
            <option key={w.id} value={w.id}>{w.branch ?? '(detached)'}</option>
          ))}
        </select>
      </label>
      <button
        disabled={isTerminal || !selectedWorktree}
        onClick={() =>
          start.mutate(
            { taskId, worktreeId: selectedWorktree },
            {
              onError: (err: unknown) =>
                setError(translateError((err as Error).message ?? String(err))),
            },
          )
        }
      >
        ▶ Iniciar sessão
      </button>
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
