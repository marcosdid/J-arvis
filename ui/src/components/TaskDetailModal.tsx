import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { queryKeys } from '../lib/query-keys';
import { isValidTransition } from '../lib/transitions';
import { translateError } from '../lib/errorMessages';
import { usePatchTask, useStartTaskSession } from '../hooks/useTaskMutations';
import { RunTab } from './RunTab';

const ALL_STATES = ['idea', 'ready', 'in_progress', 'review', 'done', 'discarded'];

type Props = { taskId: string; onClose: () => void };

function BranchEditField({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => {
    setDraft(value);
  }, [value]);

  return (
    <label>
      Branch:
      <input
        aria-label="task-branch-edit"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          if (draft !== value) onChange(draft);
        }}
        pattern="^[a-z0-9][a-z0-9._/-]*$"
        maxLength={200}
        placeholder="auto-slug do título"
      />
    </label>
  );
}

export function TaskDetailModal({ taskId, onClose }: Props) {
  const qc = useQueryClient();
  const task = useQuery({
    queryKey: queryKeys.task(taskId),
    queryFn: () => api.getTask(taskId),
  });
  const worktrees = useQuery({
    queryKey: task.data ? queryKeys.worktrees(task.data.project_id) : ['worktrees', '__pending__'],
    queryFn: () => api.listWorktrees(task.data!.project_id),
    enabled: !!task.data,
  });
  const patch = usePatchTask();
  const start = useStartTaskSession();
  const branchPatch = useMutation({
    mutationFn: (branch: string) => api.patchTask(taskId, { branch }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.tasks }),
  });

  const [titleDraft, setTitleDraft] = useState('');
  const [descDraft, setDescDraft] = useState('');
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
  const taskWorktrees = (worktrees.data ?? []).filter((w) => w.task_id === taskId);
  const hasWorktrees = taskWorktrees.length > 0;

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

      {!hasWorktrees && (
        <BranchEditField
          value={t.branch ?? ''}
          onChange={(v) => branchPatch.mutate(v)}
        />
      )}
      {hasWorktrees && t.branch && (
        <p>
          Branch: <code>{t.branch}</code> <em>(imutável após 1ª sessão)</em>
        </p>
      )}

      <h4>Sessions</h4>

      <button
        disabled={isTerminal}
        onClick={() =>
          start.mutate(
            { taskId },
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

      {hasWorktrees && (
        <details>
          <summary>Worktrees ({taskWorktrees.length})</summary>
          <ul>
            {taskWorktrees.map((w) => (
              <li key={w.id}>
                {w.repository_name && <strong>{w.repository_name}</strong>}
                : <code>{w.path}</code>
                {w.branch && <> @ <code>{w.branch}</code></>}
              </li>
            ))}
          </ul>
        </details>
      )}

      {(t.state === 'in_progress' || t.state === 'review') && (
        <details className="run-tab-details">
          <summary>Run</summary>
          <RunTab taskId={taskId} />
        </details>
      )}
    </div>
  );
}
