import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocalStorage } from '../lib/useLocalStorage';
import { api, type Project, type Task, type Worktree } from '../lib/api';
import { translateError } from '../lib/errorMessages';
import { queryKeys } from '../lib/query-keys';
import { OrphansGroup } from './OrphansGroup';
import { TaskWorktreeGroup } from './TaskWorktreeGroup';

type Props = {
  project: Project;
  onError: (msg: string) => void;
};

const ACTIVE_STATES = ['in_progress', 'review'] as const;
type ActiveState = (typeof ACTIVE_STATES)[number];

function isActiveState(s: string): s is ActiveState {
  return (ACTIVE_STATES as readonly string[]).includes(s);
}

export function ProjectNode({ project, onError }: Props) {
  const qc = useQueryClient();
  const [collapsed, setCollapsed] = useLocalStorage<boolean>(
    `jarvis.proj.${project.id}.collapsed`,
    false,
  );

  const wts = useQuery({
    queryKey: queryKeys.worktrees(project.id),
    queryFn: () => api.listWorktrees(project.id),
  });

  const tasks = useQuery({
    queryKey: queryKeys.tasksForProject(project.id),
    queryFn: () => api.listTasks([project.id]),
  });

  const del = useMutation({
    mutationFn: () => api.deleteProject(project.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.projects }),
    onError: (err: unknown) => {
      const msg = (err as Error).message ?? String(err);
      onError(translateError(msg));
    },
  });

  const allWts: Worktree[] = wts.data ?? [];
  const allTasks: Task[] = tasks.data ?? [];
  const orphans = allWts.filter((w) => w.is_orphan);
  const wtsByTask = new Map<string, Worktree[]>();
  for (const w of allWts) {
    if (w.task_id) {
      const list = wtsByTask.get(w.task_id) ?? [];
      list.push(w);
      wtsByTask.set(w.task_id, list);
    }
  }
  const activeTasksWithWts = allTasks.filter(
    (t) => isActiveState(t.state) && (wtsByTask.get(t.id)?.length ?? 0) > 0,
  );

  const repoCountLabel =
    project.repositories.length === 1
      ? 'monorepo'
      : `${project.repositories.length} sub-repos`;
  const taskLabel =
    activeTasksWithWts.length === 1
      ? '1 task ativa'
      : `${activeTasksWithWts.length} tasks ativas`;

  return (
    <section className="project-node" data-project-id={project.id}>
      <header>
        <button
          type="button"
          aria-label={collapsed ? `expand-${project.name}` : `collapse-${project.name}`}
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? '▶' : '▼'}
        </button>
        <strong>{project.name}</strong>
        <span className="meta">{repoCountLabel} · {taskLabel}</span>
        <button
          type="button"
          aria-label={`delete-${project.name}`}
          onClick={() => del.mutate()}
        >
          Excluir
        </button>
      </header>
      {!collapsed && (
        <>
          {activeTasksWithWts.map((task) => (
            <TaskWorktreeGroup
              key={task.id}
              task={task}
              worktrees={wtsByTask.get(task.id) ?? []}
            />
          ))}
          {orphans.length > 0 && (
            <OrphansGroup project={project} worktrees={orphans} onError={onError} />
          )}
        </>
      )}
    </section>
  );
}
