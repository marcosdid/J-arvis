import { useState, useEffect, type FormEvent } from 'react';
import type { Project } from '../../lib/api';
import { useCreateTask } from '../../hooks/useTaskMutations';
import { useCatalog } from '../../hooks/useCatalog';
import { InvalidBranchSlugError, slugifyForBranch } from '../../lib/slug';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';

type Props = {
  open: boolean;
  onClose: () => void;
  projects: Project[];
};

export function NewTaskSheet({ open, onClose, projects }: Props) {
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
          onClose();
        },
      },
    );
  }

  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent side="right" className="w-[480px] sm:max-w-[480px] bg-bg-surface border-l border-border-subtle">
        <SheetHeader>
          <SheetTitle className="font-display text-text-emphasis">new task</SheetTitle>
          <SheetDescription className="sr-only">
            Formulário para criar uma nova tarefa: projeto, título, descrição, branch e template.
          </SheetDescription>
        </SheetHeader>
        <form onSubmit={onSubmit} aria-label="new-task" className="new-task-form mt-4 flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-text-subtle text-xs">
            Projeto:
            <select
              aria-label="projeto"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="bg-bg-deep border border-border-subtle text-text-emphasis text-xs px-2 py-1 rounded-sm focus:outline-none focus:border-accent-primary"
            >
              {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <input
            aria-label="título"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Título"
            className="bg-bg-deep border border-border-subtle text-text-emphasis text-xs px-2 py-1 rounded-sm focus:outline-none focus:border-accent-primary"
          />
          <label className="flex flex-col gap-1 text-text-subtle text-xs">
            Template:
            <select
              aria-label="template"
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              className="bg-bg-deep border border-border-subtle text-text-emphasis text-xs px-2 py-1 rounded-sm focus:outline-none focus:border-accent-primary"
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
            <p className="hint text-xs text-text-subtle" aria-label="template-hint">{templateHint}</p>
          )}
          <textarea
            aria-label="descrição"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Descrição (opcional)"
            className="bg-bg-deep border border-border-subtle text-text-emphasis text-xs px-2 py-1 rounded-sm focus:outline-none focus:border-accent-primary resize-none min-h-[80px]"
          />
          <details>
            <summary className="text-text-subtle text-xs cursor-pointer">Avançado</summary>
            <label className="flex flex-col gap-1 text-text-subtle text-xs mt-2">
              Branch:
              <input
                aria-label="task-branch"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                placeholder={slugPreview}
                pattern="^[a-z0-9][a-z0-9._/-]*$"
                maxLength={200}
                className="bg-bg-deep border border-border-subtle text-text-emphasis text-xs px-2 py-1 rounded-sm focus:outline-none focus:border-accent-primary"
              />
            </label>
            <p className="hint text-xs text-text-faint mt-1">
              Vazio: usa slug do título. Aceita prefixos como "feature/JIRA-123".
            </p>
          </details>
          <button
            type="submit"
            disabled={!canSubmit || create.isPending}
            className="bg-accent-primary text-bg-deep text-xs font-semibold px-3 py-1.5 rounded-sm hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Criar
          </button>
        </form>
      </SheetContent>
    </Sheet>
  );
}
