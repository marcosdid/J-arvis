import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';
import { api } from '../lib/api';
import { queryKeys } from '../lib/query-keys';
import { ProjectNode } from './ProjectNode';

type Props = { open: boolean; onClose: () => void };

export function ProjectsDrawer({ open, onClose }: Props) {
  const [toast, setToast] = useState<string | null>(null);

  const projects = useQuery({
    queryKey: queryKeys.projects,
    queryFn: api.listProjects,
    enabled: open,
  });

  if (!open) return null;

  return (
    <aside role="dialog" aria-label="projects-drawer" className="drawer">
      <header>
        <h2>Projetos & Worktrees</h2>
        <button onClick={onClose} aria-label="close-drawer">✕</button>
      </header>
      <CreateProjectForm />
      {projects.data?.map((p) => (
        <ProjectNode key={p.id} project={p} onError={setToast} />
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
