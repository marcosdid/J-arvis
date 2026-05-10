import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';
import { api } from '../lib/api';
import { translateError } from '../lib/errorMessages';
import { queryKeys } from '../lib/query-keys';

type Props = { open: boolean; onClose: () => void };

export function ProjectsDrawer({ open, onClose }: Props) {
  const qc = useQueryClient();
  const [toast, setToast] = useState<string | null>(null);

  const projects = useQuery({
    queryKey: queryKeys.projects,
    queryFn: api.listProjects,
    enabled: open,
  });

  const del = useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.projects }),
    onError: (err: unknown) => {
      const msg = (err as Error).message ?? String(err);
      setToast(translateError(msg));
    },
  });

  if (!open) return null;

  return (
    <aside role="dialog" aria-label="projects-drawer" className="drawer">
      <header>
        <h2>Projetos</h2>
        <button onClick={onClose} aria-label="close-drawer">✕</button>
      </header>
      <CreateProjectForm />
      {projects.data?.map((p) => (
        <div key={p.id} className="project-row">
          <strong>{p.name}</strong>
          <code>{p.path}</code>
          <button
            aria-label={`delete-${p.name}`}
            onClick={() => del.mutate(p.id)}
          >
            Excluir
          </button>
          <WorktreesInline projectId={p.id} />
        </div>
      ))}
      {toast && (
        <p role="alert" className="toast" onClick={() => setToast(null)}>
          {toast}
        </p>
      )}
    </aside>
  );
}

function CreateProjectForm() {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [path, setPath] = useState('');

  const create = useMutation({
    mutationFn: () => api.createProject(name, path),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: queryKeys.projects });
      setName('');
      setPath('');
    },
  });

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <form aria-label="add-project" onSubmit={onSubmit}>
      <input
        aria-label="project-name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Nome"
        required
      />
      <input
        aria-label="project-path"
        value={path}
        onChange={(e) => setPath(e.target.value)}
        placeholder="Caminho"
        required
      />
      <button type="submit" disabled={create.isPending}>
        Adicionar projeto
      </button>
    </form>
  );
}

function WorktreesInline({ projectId }: { projectId: string }) {
  const qc = useQueryClient();

  const wts = useQuery({
    queryKey: queryKeys.worktrees(projectId),
    queryFn: () => api.listWorktrees(projectId),
  });

  const quickSession = useMutation({
    mutationFn: (wid: string) => api.startSession(wid),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.sessions }),
  });

  return (
    <ul>
      {wts.data?.map((w) => (
        <li key={w.id}>
          <code>{w.branch ?? '(detached)'}</code>
          <button
            aria-label={`quick-${w.branch ?? w.id}`}
            onClick={() => quickSession.mutate(w.id)}
          >
            ▶ Quick session
          </button>
        </li>
      ))}
    </ul>
  );
}
