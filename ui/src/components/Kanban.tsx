import { DndContext, closestCenter, type DragEndEvent } from '@dnd-kit/core';
import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { api, type Task, type Project } from '../lib/api';
import { isValidTransition, resolveColumnState } from '../lib/transitions';
import { translateError } from '../lib/errorMessages';
import { queryKeys } from '../lib/query-keys';
import { useTasks } from '../hooks/useTasks';
import { usePatchTask } from '../hooks/useTaskMutations';
import { KanbanColumn } from './KanbanColumn';

const COLUMNS = ['Backlog', 'In Progress', 'Review', 'Done', 'Discarded'] as const;

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

  return (
    <>
      {error && (
        <div role="alert" className="toast" onClick={() => setError(null)}>
          {error}
        </div>
      )}
      <DndContext collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <div className="kanban">
          {COLUMNS.map((col) => (
            <KanbanColumn
              key={col}
              name={col}
              tasks={buckets[col]}
              projects={projectMap}
              {...(onCardClick ? { onCardClick } : {})}
            />
          ))}
        </div>
      </DndContext>
    </>
  );
}
