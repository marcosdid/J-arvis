import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import type { Task, Project } from '../lib/api';
import { TaskCard } from './TaskCard';

type Props = {
  name: string;
  tasks: Task[];
  projects: Map<string, Project>;
  onCardClick?: (id: string) => void;
};

export function KanbanColumn({ name, tasks, projects, onCardClick }: Props) {
  // PFC-7: prefix column IDs to avoid collision with task IDs
  const { setNodeRef } = useDroppable({ id: `column:${name}` });
  return (
    <div
      ref={setNodeRef}
      className="kanban-column"
      data-testid={`column-${name}`}
    >
      <h3>{name}</h3>
      <SortableContext
        items={tasks.map((t) => t.id)}
        strategy={verticalListSortingStrategy}
      >
        {tasks.map((t) => (
          <TaskCard
            key={t.id}
            task={t}
            projects={projects}
            onClick={() => onCardClick?.(t.id)}
          />
        ))}
      </SortableContext>
    </div>
  );
}
