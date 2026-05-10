import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { Task, Project } from '../lib/api';
import { projectColor } from '../lib/projectColor';

type Props = {
  task: Task;
  projects: Map<string, Project>;
  onClick?: () => void;
};

export function TaskCard({ task, projects, onClick }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: task.id });
  const project = projects.get(task.project_id);
  const subTag =
    task.state === 'idea' || task.state === 'ready' ? task.state : null;

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
      }}
      className="task-card"
      data-task-id={task.id}
      onClick={onClick}
      {...attributes}
      {...listeners}
    >
      <span
        className="project-chip"
        style={{ backgroundColor: projectColor(task.project_id) }}
      >
        ● {project?.name ?? task.project_id.slice(0, 6)}
      </span>
      <h4>{task.title}</h4>
      {subTag && <span className="sub-tag">{subTag}</span>}
    </div>
  );
}
