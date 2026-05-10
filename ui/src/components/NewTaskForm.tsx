import { useState, useEffect, type FormEvent } from 'react';
import type { Project } from '../lib/api';
import { useCreateTask } from '../hooks/useTaskMutations';

type Props = { projects: Project[] };

export function NewTaskForm({ projects }: Props) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [projectId, setProjectId] = useState(projects[0]?.id ?? '');
  const create = useCreateTask();

  const canSubmit = title.trim().length > 0 && projectId !== '';

  // Sync default when projects list arrives late (e.g. async load)
  useEffect(() => {
    if (!projectId && projects[0]) setProjectId(projects[0].id);
  }, [projects]);

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    create.mutate(
      { project_id: projectId, title, description },
      { onSuccess: () => { setTitle(''); setDescription(''); } },
    );
  }

  return (
    <form onSubmit={onSubmit} aria-label="new-task" className="new-task-form">
      <label>
        Projeto:
        <select
          aria-label="projeto"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </label>
      <input
        aria-label="título"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Título"
      />
      <textarea
        aria-label="descrição"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Descrição (opcional)"
      />
      <button type="submit" disabled={!canSubmit || create.isPending}>
        Criar
      </button>
    </form>
  );
}
