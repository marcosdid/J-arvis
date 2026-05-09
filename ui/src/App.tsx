import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';

import {
  api,
  type Project,
  type Session,
  type Worktree,
} from './lib/api';
import { formatStatus } from './lib/format';
import { queryKeys } from './lib/query-keys';
import { useSessionEvents } from './hooks/useSessionEvents';

export function App() {
  const queryClient = useQueryClient();
  useSessionEvents(queryClient);
  return (
    <main>
      <h1>J-arvis</h1>
      <ProjectsSection />
    </main>
  );
}

function ProjectsSection() {
  const projects = useQuery({
    queryKey: queryKeys.projects,
    queryFn: api.listProjects,
  });

  return (
    <section aria-label="projects">
      <h2>Projetos</h2>
      <AddProjectForm />
      {projects.isLoading && <p>Carregando…</p>}
      {projects.isError && <p role="alert">Erro: {String(projects.error)}</p>}
      <ul>
        {projects.data?.map((project) => (
          <ProjectItem key={project.id} project={project} />
        ))}
      </ul>
    </section>
  );
}

function AddProjectForm() {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [path, setPath] = useState('');

  const addProject = useMutation({
    mutationFn: () => api.createProject(name, path),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.projects });
      setName('');
      setPath('');
    },
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    addProject.mutate();
  }

  return (
    <form onSubmit={onSubmit} aria-label="add-project">
      <input
        aria-label="project-name"
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Nome"
        required
      />
      <input
        aria-label="project-path"
        value={path}
        onChange={(event) => setPath(event.target.value)}
        placeholder="Caminho"
        required
      />
      <button type="submit" disabled={addProject.isPending}>
        Adicionar projeto
      </button>
      {addProject.isError && (
        <p role="alert">Erro: {String(addProject.error)}</p>
      )}
    </form>
  );
}

function ProjectItem({ project }: { project: Project }) {
  const queryClient = useQueryClient();
  const worktrees = useQuery({
    queryKey: queryKeys.worktrees(project.id),
    queryFn: () => api.listWorktrees(project.id),
  });

  const deleteProject = useMutation({
    mutationFn: () => api.deleteProject(project.id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.projects }),
  });

  return (
    <li className="project">
      <header>
        <h3>{project.name}</h3>
        <code>{project.path}</code>
        <button onClick={() => deleteProject.mutate()} aria-label={`delete-${project.name}`}>
          Excluir
        </button>
      </header>
      <h4>Worktrees</h4>
      {worktrees.isLoading && <p>Carregando worktrees…</p>}
      <ul>
        {worktrees.data?.map((worktree) => (
          <WorktreeItem key={worktree.id} worktree={worktree} />
        ))}
      </ul>
      <SessionsSection worktrees={worktrees.data ?? []} />
    </li>
  );
}

function WorktreeItem({ worktree }: { worktree: Worktree }) {
  const queryClient = useQueryClient();
  const startSession = useMutation({
    mutationFn: () => api.startSession(worktree.id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.sessions }),
  });

  return (
    <li className="worktree">
      <span className="branch">{worktree.branch ?? '(detached)'}</span>{' '}
      <code>{worktree.path}</code>
      <button
        onClick={() => startSession.mutate()}
        disabled={startSession.isPending}
        aria-label={`start-${worktree.branch ?? worktree.id}`}
      >
        ▶ Nova sessão
      </button>
    </li>
  );
}

function SessionsSection({ worktrees }: { worktrees: Worktree[] }) {
  const sessions = useQuery({
    queryKey: queryKeys.sessions,
    queryFn: api.listSessions,
  });
  const ids = new Set(worktrees.map((worktree) => worktree.id));
  const filtered = (sessions.data ?? []).filter((session) =>
    ids.has(session.worktree_id),
  );
  if (filtered.length === 0) {
    return null;
  }
  return (
    <>
      <h4>Sessões</h4>
      <ul>
        {filtered.map((session) => (
          <SessionItem key={session.id} session={session} />
        ))}
      </ul>
    </>
  );
}

function SessionItem({ session }: { session: Session }) {
  const queryClient = useQueryClient();
  const stopSession = useMutation({
    mutationFn: () => api.stopSession(session.id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.sessions }),
  });

  const isLive = session.status !== 'done' && session.status !== 'error';

  return (
    <li className="session" data-status={session.status}>
      <code>#{session.id.slice(0, 8)}</code>
      {' — '}
      <span>{formatStatus(session.status)}</span>
      {isLive && (
        <button
          onClick={() => stopSession.mutate()}
          disabled={stopSession.isPending}
          aria-label={`stop-${session.id}`}
        >
          Stop
        </button>
      )}
    </li>
  );
}
