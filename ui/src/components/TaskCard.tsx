import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { Task, Project } from '../lib/api';
import { projectColor } from '../lib/projectColor';
import { RunStatus } from './RunStatus';

type Props = {
  task: Task;
  projects: Map<string, Project>;
  onClick?: () => void;
};

const PROFILE_COLORS: Record<string, string> = {
  yolo: 'yellow',
  default: 'gray',
  'read-only': 'green',
};

function profileColor(name: string): string {
  return PROFILE_COLORS[name] ?? 'gray';
}

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
      {task.template && (
        <span
          data-template-name={task.template}
          data-testid="template-badge"
          className="template-badge"
        >
          {task.template}
        </span>
      )}
      {task.permission_profile && (
        <span
          data-permission-profile={task.permission_profile}
          data-profile-color={profileColor(task.permission_profile)}
          data-testid="profile-badge"
          className={`profile-badge profile-${profileColor(task.permission_profile)}`}
          title={`Perfil: ${task.permission_profile}`}
        >
          {task.permission_profile}
        </span>
      )}
      {subTag && <span className="sub-tag">{subTag}</span>}
      {(task.state === 'in_progress' || task.state === 'review') && (
        <RunStatus taskId={task.id} />
      )}
    </div>
  );
}
