import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { api, type Task, type Project } from '../../lib/api';
import { isValidTransition, resolveColumnState } from '../../lib/transitions';
import { translateError } from '../../lib/errorMessages';
import { queryKeys } from '../../lib/query-keys';
import { useTasks } from '../../hooks/useTasks';
import { usePatchTask } from '../../hooks/useTaskMutations';
import { KanbanColumn } from './KanbanColumn';
import { TaskCardSkeleton } from './TaskCardSkeleton';

const COLUMNS = ['Backlog', 'In Progress', 'Review', 'Done', 'Discarded'] as const;
const SKELETON_COUNT = 4;

type Column = (typeof COLUMNS)[number];

function bucketize(tasks: Task[]): Record<Column, Task[]> {
  const buckets = Object.fromEntries(
    COLUMNS.map((c) => [c, [] as Task[]])
  ) as Record<Column, Task[]>;
  for (const t of tasks) {
    if (t.state === 'idea' || t.state === 'ready') buckets.Backlog.push(t);
    else if (t.state === 'in_progress') buckets['In Progress'].push(t);
    else if (t.state === 'review') buckets.Review.push(t);
    else if (t.state === 'done') buckets.Done.push(t);
    else if (t.state === 'discarded') buckets.Discarded.push(t);
  }
  return buckets;
}

function stateToColumn(state: string): string {
  if (state === 'idea' || state === 'ready') return 'Backlog';
  if (state === 'in_progress') return 'In Progress';
  if (state === 'review') return 'Review';
  if (state === 'done') return 'Done';
  return 'Discarded';
}

type Props = {
  filters: string[];
  onCardClick?: (id: string) => void;
};

export function Kanban({ filters, onCardClick }: Props) {
  // 8-px activation distance preserves card-click semantics (dnd-kit's
  // default PointerSensor activates on any pointer-down and its
  // preventDefault() suppresses the synthesized React onClick).
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );
  const tasks = useTasks(filters.length ? filters : undefined);
  const projects = useQuery({
    queryKey: queryKeys.projects,
    queryFn: api.listProjects,
  });
  const patch = usePatchTask();
  const [error, setError] = useState<string | null>(null);

  const projectMap = new Map<string, Project>(
    (projects.data ?? []).map((p) => [p.id, p])
  );
  const taskById = new Map<string, Task>(
    (tasks.data ?? []).map((t) => [t.id, t])
  );
  const buckets = bucketize(tasks.data ?? []);

  function handleDragEnd(taskId: string, column: string): void {
    const task = taskById.get(taskId);
    if (!task) return;
    const target = resolveColumnState(column);
    if (target === task.state) return;
    if (!isValidTransition(task.state, target)) {
      setError('Transição não permitida.');
      return;
    }
    patch.mutate(
      { id: taskId, patch: { state: target } },
      {
        onError: (err: unknown) => setError(
          translateError((err as Error).message ?? String(err))
        ),
      },
    );
  }

  function onDragEnd(e: DragEndEvent): void {
    const taskId = String(e.active.id);
    const overId = e.over ? String(e.over.id) : null;
    if (!overId) return;
    let columnName: string;
    if (overId.startsWith('column:')) {
      columnName = overId.slice('column:'.length);
    } else {
      // overId is a task.id; find its column
      const overTask = taskById.get(overId);
      if (!overTask) return;
      columnName = stateToColumn(overTask.state);
    }
    handleDragEnd(taskId, columnName);
  }

  // PFC-10: test seam, env-gated — never in production
  const handleDragEndRef = useRef(handleDragEnd);
  useEffect(() => {
    handleDragEndRef.current = handleDragEnd;
  });
  useEffect(() => {
    if (import.meta.env.MODE !== 'test') return;
    function fromCustom(ev: Event): void {
      const detail = (ev as CustomEvent).detail;
      handleDragEndRef.current(detail.taskId, detail.column);
    }
    window.addEventListener('test:dragEnd', fromCustom);
    return () => window.removeEventListener('test:dragEnd', fromCustom);
  }, []);

  if (tasks.isLoading) {
    return (
      <div className="flex gap-3 p-3 h-full overflow-x-auto" data-testid="kanban-loading">
        {COLUMNS.map((col) => (
          <div key={col} className="flex flex-col gap-2 min-w-[200px]">
            {Array.from({ length: SKELETON_COUNT }, (_, i) => (
              <TaskCardSkeleton key={i} />
            ))}
          </div>
        ))}
      </div>
    );
  }

  if ((tasks.data ?? []).length === 0) {
    return (
      <div className="flex items-center justify-center h-full" data-testid="kanban-empty-state">
        <div className="border border-border-subtle p-8 text-center text-text-subtle relative">
          <pre className="text-text-faint text-xs leading-tight mb-3">
{`┌─────────────────┐
│   no tasks yet  │
└─────────────────┘`}
          </pre>
          <p className="text-xs">
            Create a task to get started — press <kbd className="text-accent-primary">[N]</kbd> or click <span className="text-accent-primary">+ new task</span> above.
          </p>
        </div>
      </div>
    );
  }

  return (
    <>
      {error && (
        <div
          role="alert"
          className="fixed top-3 left-1/2 -translate-x-1/2 z-50 bg-sem-error/10 border border-sem-error text-sem-error text-xs px-4 py-2 rounded-sm cursor-pointer"
          onClick={() => setError(null)}
        >
          {error}
        </div>
      )}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <div className="flex gap-3 p-3 h-full overflow-x-auto">
          {COLUMNS.map((col) => (
            <KanbanColumn
              key={col}
              name={col}
              tasks={buckets[col]}
              projects={projectMap}
              {...(projects.data?.[0]?.id ? { defaultProjectId: projects.data[0].id } : {})}
              {...(onCardClick ? { onCardClick } : {})}
            />
          ))}
        </div>
      </DndContext>
    </>
  );
}
