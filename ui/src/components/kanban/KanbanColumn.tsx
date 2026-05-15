import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import type { Task, Project } from '../../lib/api';
import { TaskCard } from './TaskCard';
import { NewTaskInline } from './NewTaskInline';

const COLUMN_STATES: Record<string, string> = {
  Backlog: 'idea',
  'In Progress': 'in_progress',
  Review: 'review',
  Done: 'done',
  Discarded: 'discarded',
};

type Props = {
  name: string;
  tasks: Task[];
  projects: Map<string, Project>;
  defaultProjectId?: string;
  onCardClick?: (id: string) => void;
};

export function KanbanColumn({ name, tasks, projects, defaultProjectId, onCardClick }: Props) {
  // PFC-7: prefix column IDs to avoid collision with task IDs
  const { setNodeRef } = useDroppable({ id: `column:${name}` });
  return (
    <div
      ref={setNodeRef}
      className="flex flex-col min-w-[260px] bg-bg-surface border border-border-subtle rounded-sm"
      data-testid={`column-${name}`}
    >
      <h3 className="font-display tracking-[0.08em] text-text-emphasis uppercase text-xs px-3 py-2 border-b border-border-subtle bg-bg-deep">
        {name}
      </h3>
      <SortableContext
        items={tasks.map((t) => t.id)}
        strategy={verticalListSortingStrategy}
      >
        <div className="flex flex-col gap-2 p-2 overflow-y-auto">
          {tasks.map((t) => (
            <TaskCard
              key={t.id}
              task={t}
              projects={projects}
              onClick={() => onCardClick?.(t.id)}
            />
          ))}
        </div>
      </SortableContext>
      {defaultProjectId && (
        <div className="p-2 border-t border-border-subtle">
          <NewTaskInline
            columnState={COLUMN_STATES[name] ?? 'idea'}
            projectId={defaultProjectId}
          />
        </div>
      )}
    </div>
  );
}
