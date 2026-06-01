import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, type Task, type Project } from '../../lib/api';
import { projectColor } from '../../lib/projectColor';
import { queryKeys } from '../../lib/query-keys';
import { formatRelativeTime } from '../../lib/relativeTime';
import { useCatalog } from '../../hooks/useCatalog';
import { useRun } from '../../hooks/useRun';
import { useSandboxHealth } from '../../hooks/useSandboxHealth';
import { useSessions } from '../../hooks/useSessions';
import { cn } from '../../lib/utils';
import { RunStatus } from '../RunStatus';
import { SessionPanel } from '../sessions/SessionPanel';
import { SessionStatusChip } from '../sessions/SessionStatusChip';
import { deriveCardState } from './taskCardState';

const TEMPLATE_COLORS: Record<string, string> = {
  backend: 'var(--semantic-backend)',
  frontend: 'var(--semantic-frontend)',
  bugfix: 'var(--semantic-bugfix)',
  refactor: 'var(--semantic-refactor)',
  review: 'var(--semantic-review)',
  ops: 'var(--text-subtle)',
  research: 'var(--accent-info)',
};

function templateColor(name: string | null): string {
  if (!name) return 'var(--text-subtle)';
  return TEMPLATE_COLORS[name] ?? 'var(--text-subtle)';
}

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

  const projName = project?.name ?? task.project_id.slice(0, 6);
  const projHue = projectColor(task.project_id);
  const shortId = task.id.replace(/-/g, '').slice(0, 4);
  const relTime = formatRelativeTime(task.updated_at || task.created_at);

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
      }}
      className={cn(
        'group flex flex-col gap-3 bg-bg-elevated border border-border-subtle rounded-md px-4 py-3.5 cursor-grab hover:border-border-mid transition-colors duration-[180ms] ease-out',
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
      <header className="flex items-center justify-between gap-3">
        <span
          className="inline-flex items-center min-w-0 font-mono text-xs tracking-tight"
          style={{ color: projHue }}
        >
          <span className="truncate">● {projName}</span>
        </span>
        <span className="font-mono text-[11px] text-text-faint shrink-0">
          #{shortId}
        </span>
      </header>

      <h4 className="font-display text-[15px] font-medium leading-snug text-text-title">
        {task.title}
      </h4>

      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-xs">
        {task.template && (
          <span
            data-template-name={task.template}
            data-testid="template-badge"
            title={templateDescription ?? task.template}
            className="inline-flex items-center gap-1.5 rounded-sm border border-border-subtle bg-bg-deep px-2 py-0.5 font-mono text-[11px] text-text-emphasis"
          >
            <span
              aria-hidden
              className="inline-block h-2 w-2 rounded-[1px]"
              style={{ backgroundColor: templateColor(task.template) }}
            />
            {task.template}
          </span>
        )}
        {task.permission_profile && (
          <span
            data-permission-profile={task.permission_profile}
            data-profile-color={profileColor(task.permission_profile)}
            data-testid="profile-badge"
            title={profileDescription ?? `Perfil: ${task.permission_profile}`}
            className="inline-flex items-center rounded-sm border border-border-subtle bg-bg-deep px-2 py-0.5 font-mono text-[11px] text-text-subtle"
          >
            {task.permission_profile}
          </span>
        )}
        {subTag && (
          <span className="inline-flex items-center rounded-sm border border-border-subtle bg-bg-deep px-2 py-0.5 font-mono text-[11px] text-text-subtle">
            {subTag}
          </span>
        )}
        <span aria-hidden className="text-text-faint">·</span>
        <span className="font-mono text-[11px] text-text-faint" title={task.updated_at}>
          {relTime}
        </span>
      </div>

      {(task.state === 'in_progress' || task.state === 'review') && (
        <RunStatus taskId={task.id} />
      )}

      <footer className="flex items-center justify-between gap-2 pt-2 border-t border-border-subtle/60">
        {activeSession ? (
          <button
            type="button"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation();
              setPanelOpen(true);
            }}
            className="inline-flex items-center gap-2"
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
            className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-accent-primary transition-opacity hover:opacity-80 disabled:opacity-40 disabled:cursor-not-allowed"
            data-testid="task-session-start"
          >
            <span aria-hidden>▶</span>
            <span>iniciar sessão</span>
          </button>
        )}
      </footer>

      <SessionPanel taskId={task.id} open={panelOpen} onOpenChange={setPanelOpen} />
    </div>
  );
}
