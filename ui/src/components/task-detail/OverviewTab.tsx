import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api, type Task } from '../../lib/api';
import { queryKeys } from '../../lib/query-keys';
import { isValidTransition } from '../../lib/transitions';
import { translateError } from '../../lib/errorMessages';
import { usePatchTask, useStartTaskSession } from '../../hooks/useTaskMutations';

const ALL_STATES = ['idea', 'ready', 'in_progress', 'review', 'done', 'discarded'];

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

type Props = { task: Task };

export function OverviewTab({ task }: Props) {
  const qc = useQueryClient();
  const worktrees = useQuery({
    queryKey: queryKeys.worktrees(task.project_id),
    queryFn: () => api.listWorktrees(task.project_id),
  });
  const patch = usePatchTask();
  const start = useStartTaskSession();
  const branchPatch = useMutation({
    mutationFn: (branch: string) => api.patchTask(task.id, { branch }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.tasks }),
  });

  const [titleDraft, setTitleDraft] = useState(task.title);
  const [descDraft, setDescDraft] = useState(task.description);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setTitleDraft(task.title);
    setDescDraft(task.description);
  }, [task.id, task.title, task.description]);

  // Debounced PATCH for title/description
  useEffect(() => {
    if (titleDraft === task.title && descDraft === task.description) return;
    if (!titleDraft.trim()) return;
    const tid = setTimeout(() => {
      const update: Record<string, string> = {};
      if (titleDraft !== task.title) update.title = titleDraft;
      if (descDraft !== task.description) update.description = descDraft;
      if (Object.keys(update).length === 0) return;
      patch.mutate({ id: task.id, patch: update });
    }, 500);
    return () => clearTimeout(tid);
    // deps limited to draft values — task read via closure, not as a trigger
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [titleDraft, descDraft]);

  const moveTargets = ALL_STATES.filter(
    (s) => s !== task.state && isValidTransition(task.state, s),
  );

  const isTerminal = task.state === 'done' || task.state === 'discarded';
  const taskWorktrees = (worktrees.data ?? []).filter((w) => w.task_id === task.id);
  const hasWorktrees = taskWorktrees.length > 0;

  return (
    <div>
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
            patch.mutate({ id: task.id, patch: { state: e.target.value } });
          }}
        >
          <option value="">—</option>
          {moveTargets.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>

      {!hasWorktrees && (
        <BranchEditField
          value={task.branch ?? ''}
          onChange={(v) => branchPatch.mutate(v)}
        />
      )}
      {hasWorktrees && task.branch && (
        <p>
          Branch: <code>{task.branch}</code> <em>(imutável após 1ª sessão)</em>
        </p>
      )}

      <section aria-label="task-config">
        <h3>Configuração</h3>
        <dl>
          <dt>Template</dt>
          <dd>{task.template ?? '(nenhum)'}</dd>
          <dt>Perfil de permissão</dt>
          <dd>{task.permission_profile ?? '(fallback)'}</dd>
          <dt>Branch</dt>
          <dd>{task.branch ?? '(será derivado no spawn)'}</dd>
        </dl>
      </section>

      <button
        disabled={isTerminal}
        onClick={() =>
          start.mutate(
            { taskId: task.id },
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
    </div>
  );
}
