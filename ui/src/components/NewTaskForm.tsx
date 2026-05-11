import { useState, useEffect, type FormEvent } from 'react';
import type { Project } from '../lib/api';
import { useCreateTask } from '../hooks/useTaskMutations';
import { useCatalog } from '../hooks/useCatalog';
import { InvalidBranchSlugError, slugifyForBranch } from '../lib/slug';

type Props = { projects: Project[] };

export function NewTaskForm({ projects }: Props) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [branch, setBranch] = useState('');
  const [template, setTemplate] = useState<string>('');
  const [projectId, setProjectId] = useState(projects[0]?.id ?? '');
  const create = useCreateTask();
  const catalogQ = useCatalog();

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

  const selectedTemplate = catalogQ.data?.templates.find((t) => t.name === template);

  const templateHint = (() => {
    if (!selectedTemplate) return '';
    if (branch.trim() !== '') return 'Branch override — prefix do template ignorado';
    try {
      return `Branch será: ${selectedTemplate.branch_prefix}${slugifyForBranch(title)}`;
    } catch (e) {
      if (e instanceof InvalidBranchSlugError) {
        return `Branch será: ${selectedTemplate.branch_prefix}<slug-do-título>`;
      }
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
        ...(template && { template }),
      },
      {
        onSuccess: () => {
          setTitle('');
          setDescription('');
          setBranch('');
          setTemplate('');
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
      <label>
        Template:
        <select
          aria-label="template"
          value={template}
          onChange={(e) => setTemplate(e.target.value)}
        >
          <option value="">(nenhum)</option>
          {catalogQ.data?.templates.map((t) => (
            <option key={t.name} value={t.name} data-template-name={t.name}>
              {t.name} — {t.description}
            </option>
          ))}
        </select>
      </label>
      {templateHint && (
        <p className="hint" aria-label="template-hint">{templateHint}</p>
      )}
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
