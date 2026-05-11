import { useState, useEffect, type FormEvent } from 'react';
import type { Project } from '../lib/api';
import { useCreateTask } from '../hooks/useTaskMutations';
import { InvalidBranchSlugError, slugifyForBranch } from '../lib/slug';

type Props = { projects: Project[] };

export function NewTaskForm({ projects }: Props) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [branch, setBranch] = useState('');
  const [projectId, setProjectId] = useState(projects[0]?.id ?? '');
  const create = useCreateTask();

  const canSubmit = title.trim().length > 0 && projectId !== '';

  useEffect(() => {
    if (!projectId && projects[0]) setProjectId(projects[0].id);
  }, [projects]);

  const slugPreview = (() => {
    try {
      return slugifyForBranch(title);
    } catch (e) {
      if (e instanceof InvalidBranchSlugError) return 'auto-slug do título';
      throw e;
    }
  })();

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmedBranch = branch.trim();
    create.mutate(
      {
        project_id: projectId,
        title,
        description,
        ...(trimmedBranch && { branch: trimmedBranch }),
      },
      {
        onSuccess: () => {
          setTitle('');
          setDescription('');
          setBranch('');
        },
      },
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
      <details>
        <summary>Avançado</summary>
        <label>
          Branch:
          <input
            aria-label="task-branch"
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
            placeholder={slugPreview}
            pattern="^[a-z0-9][a-z0-9._/-]*$"
            maxLength={200}
          />
        </label>
        <p className="hint">
          Vazio: usa slug do título. Aceita prefixos como "feature/JIRA-123".
        </p>
      </details>
      <button type="submit" disabled={!canSubmit || create.isPending}>
        Criar
      </button>
    </form>
  );
}
