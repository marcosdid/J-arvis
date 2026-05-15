import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, type Task, type Project } from '../../lib/api';
import { projectColor } from '../../lib/projectColor';
import { queryKeys } from '../../lib/query-keys';
import { useCatalog } from '../../hooks/useCatalog';
import { useRun } from '../../hooks/useRun';
import { useSandboxHealth } from '../../hooks/useSandboxHealth';
import { useSessions } from '../../hooks/useSessions';
import { cn } from '../../lib/utils';
import { RunStatus } from '../RunStatus';
import { SessionPanel } from '../sessions/SessionPanel';
import { SessionStatusChip } from '../sessions/SessionStatusChip';
import { deriveCardState } from './taskCardState';

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
  const catalogQ = useCatalog();
  const runQ = useRun(task.id);
  const templateDescription = catalogQ.data?.templates.find(
    (t) => t.name === task.template,
  )?.description;
  const profileDescription = catalogQ.data?.permission_profiles.find(
    (p) => p.name === task.permission_profile,
  )?.description;
  const subTag =
    task.state === 'idea' || task.state === 'ready' ? task.state : null;

  const cardState = deriveCardState(task, runQ.data?.status ?? null);

  const [panelOpen, setPanelOpen] = useState(false);
  const queryClient = useQueryClient();
  const { data: sandbox } = useSandboxHealth();
  const sandboxAvailable = sandbox?.sandbox_available ?? false;
  const sandboxReason = sandbox?.sandbox_reason ?? '';
  const { data: sessions = [] } = useSessions(task.id);
  const activeSession = sessions.find((s) => s.ended_at == null);
  const startMut = useMutation({
    mutationFn: () => api.startSession(task.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.sessionsForTask(task.id) });
      setPanelOpen(true);
    },
  });

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
      }}
      className={cn(
        'bg-bg-elevated border border-border-subtle rounded-sm p-2 cursor-grab hover:border-border-mid transition-colors duration-[180ms] ease-out',
        'data-[card-state=awaiting]:border-accent-attn data-[card-state=awaiting]:shadow-[0_0_8px_rgba(255,16,240,0.4)]',
        'data-[card-state=running]:border-accent-primary',
        'data-[card-state=error]:border-sem-error data-[card-state=error]:bg-sem-error/5',
        'data-[card-state=done]:opacity-60',
      )}
      data-task-id={task.id}
      data-card-state={cardState.kind}
      onClick={onClick}
      {...attributes}
      {...listeners}
    >
      <div className="flex items-center gap-1 mb-1">
        <span
          className="inline-flex items-center gap-1 text-[0.65rem] tracking-wide"
          style={{ backgroundColor: projectColor(task.project_id) }}
        >
          ● {project?.name ?? task.project_id.slice(0, 6)}
        </span>
        <span className="font-mono text-[0.6rem] text-text-faint">
          #{task.id.replace(/-/g, '').slice(0, 4)}
        </span>
      </div>
      <h4 className="font-display tracking-tight text-text-emphasis text-sm leading-snug">
        {task.title}
      </h4>
      {task.template && (
        <span
          data-template-name={task.template}
          data-testid="template-badge"
          className="inline-block text-[0.6rem] px-1 py-0.5 rounded-sm bg-bg-deep border border-border-subtle text-text-subtle"
          title={templateDescription ?? task.template}
        >
          {task.template}
        </span>
      )}
      {task.permission_profile && (
        <span
          data-permission-profile={task.permission_profile}
          data-profile-color={profileColor(task.permission_profile)}
          data-testid="profile-badge"
          className="inline-block text-[0.6rem] px-1 py-0.5 rounded-sm bg-bg-deep border border-border-subtle text-text-subtle"
          title={profileDescription ?? `Perfil: ${task.permission_profile}`}
        >
          {task.permission_profile}
        </span>
      )}
      {subTag && (
        <span className="inline-block text-[0.6rem] px-1 py-0.5 rounded-sm bg-bg-deep border border-border-subtle text-text-subtle">
          {subTag}
        </span>
      )}
      {(task.state === 'in_progress' || task.state === 'review') && (
        <RunStatus taskId={task.id} />
      )}
      <div className="mt-2">
        {activeSession ? (
          <button
            type="button"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation();
              setPanelOpen(true);
            }}
            className="text-xs flex items-center gap-2"
            data-testid="task-session-open"
          >
            <SessionStatusChip session={activeSession} />
          </button>
        ) : (
          <button
            type="button"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation();
              startMut.mutate();
            }}
            disabled={!sandboxAvailable || startMut.isPending}
            title={!sandboxAvailable ? sandboxReason : ''}
            className="text-xs underline disabled:opacity-50"
            data-testid="task-session-start"
          >
            ▶ Iniciar sessão
          </button>
        )}
      </div>
      <SessionPanel taskId={task.id} open={panelOpen} onOpenChange={setPanelOpen} />
    </div>
  );
}
