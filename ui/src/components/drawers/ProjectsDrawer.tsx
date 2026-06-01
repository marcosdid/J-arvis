import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';
import { AlertCircle, FolderOpen, FolderPlus, Loader2, Plus } from 'lucide-react';
import { api } from '../../lib/api';
import { queryKeys } from '../../lib/query-keys';
import { ProjectNode } from '../ProjectNode';
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';

type Props = { open: boolean; onClose: () => void };

export function ProjectsDrawer({ open, onClose }: Props) {
  const [toast, setToast] = useState<string | null>(null);

  const projects = useQuery({
    queryKey: queryKeys.projects,
    queryFn: api.listProjects,
    enabled: open,
  });

  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent side="left" className="w-[480px] sm:max-w-[480px] bg-bg-surface border-r border-border-subtle p-8 gap-8 flex flex-col overflow-y-auto">
        <SheetHeader className="space-y-3 pb-2">
          <SheetTitle className="font-display text-text-title tracking-[0.06em] uppercase text-lg">
            Projetos & Worktrees
          </SheetTitle>
          <SheetDescription className="sr-only">
            Lista de projetos cadastrados e formulário para criar novos worktrees.
          </SheetDescription>
        </SheetHeader>
        <SheetClose asChild>
          <button onClick={onClose} aria-label="close-drawer" className="sr-only">✕</button>
        </SheetClose>
        <CreateProjectForm />
        {projects.data?.map((p) => (
          <ProjectNode key={p.id} project={p} onError={setToast} />
        ))}
        {toast && (
          <p role="alert" className="toast" onClick={() => setToast(null)}>
            {toast}
          </p>
        )}
      </SheetContent>
    </Sheet>
  );
}

function CreateProjectForm() {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [path, setPath] = useState('');
  const [browseError, setBrowseError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => api.createProject(name, path),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: queryKeys.projects });
      setName('');
      setPath('');
      setBrowseError(null);
    },
  });

  async function onBrowse() {
    setBrowseError(null);
    try {
      const picked = await api.chooseDirectory();
      if (picked) setPath(picked); // empty string = user cancelled
    } catch (err) {
      const msg = (err as Error)?.message ?? String(err);
      setBrowseError(msg);
    }
  }

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    create.mutate();
  }

  const submitError = create.isError ? (create.error as Error).message : null;
  const disabled = create.isPending;

  return (
    <form
      aria-label="add-project"
      onSubmit={onSubmit}
      className="rounded-xl border border-border-subtle bg-bg-elevated/60 backdrop-blur-sm shadow-[0_0_0_1px_rgba(74,222,128,0.03)]"
    >
      <header className="flex items-center gap-3 border-b border-border-subtle px-7 py-5 text-text-title">
        <FolderPlus size={20} className="text-accent-primary" aria-hidden />
        <span className="font-display text-base tracking-[0.06em] uppercase">
          Novo projeto
        </span>
        <span aria-hidden className="ml-auto font-mono text-sm text-text-faint">
          [ + ]
        </span>
      </header>

      <fieldset disabled={disabled} className="space-y-8 px-7 py-8 disabled:opacity-60">
        <Field
          id="cp-name"
          label="Nome"
          hint="identificador curto"
        >
          <input
            id="cp-name"
            aria-label="project-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="ex.: jarvis"
            required
            className="w-full bg-bg-deep border border-border-subtle rounded-md px-4 py-3.5 text-[15px] font-mono text-text-emphasis placeholder:text-text-faint outline-none transition-colors focus:border-accent-primary focus:shadow-[0_0_0_1px_var(--accent-primary)]"
          />
        </Field>

        <Field
          id="cp-path"
          label="Caminho"
          hint="raiz do repositório local"
        >
          <div className="flex gap-3">
            <input
              id="cp-path"
              aria-label="project-path"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/home/voce/codigo/projeto"
              required
              className="flex-1 min-w-0 bg-bg-deep border border-border-subtle rounded-md px-4 py-3.5 text-[15px] font-mono text-text-emphasis placeholder:text-text-faint outline-none transition-colors focus:border-accent-primary focus:shadow-[0_0_0_1px_var(--accent-primary)]"
            />
            <button
              type="button"
              aria-label="browse-project-path"
              onClick={onBrowse}
              title="Selecionar pasta"
              className="shrink-0 inline-flex items-center justify-center gap-2 rounded-md border border-border-subtle bg-bg-deep px-4 py-3.5 text-sm uppercase tracking-[0.08em] text-text-subtle transition-colors hover:border-accent-primary hover:text-accent-primary focus:outline-none focus:border-accent-primary focus:text-accent-primary"
            >
              <FolderOpen size={16} aria-hidden />
              <span>Pasta</span>
            </button>
          </div>
          {browseError && (
            <p role="alert" className="mt-3 flex items-center gap-2 text-sm text-sem-error">
              <AlertCircle size={14} aria-hidden />
              {browseError}
            </p>
          )}
        </Field>

        <button
          type="submit"
          disabled={disabled}
          className="group relative w-full inline-flex items-center justify-center gap-3 rounded-md border border-accent-primary/70 bg-accent-primary/10 px-5 py-4 font-display text-[15px] uppercase tracking-[0.08em] text-accent-primary transition-all hover:bg-accent-primary/20 hover:border-accent-primary focus:outline-none focus:bg-accent-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {create.isPending ? (
            <Loader2 size={18} className="animate-spin" aria-hidden />
          ) : (
            <Plus size={18} aria-hidden />
          )}
          <span>Adicionar projeto</span>
        </button>

        {submitError && (
          <p role="alert" className="flex items-start gap-2 text-sm text-sem-error">
            <AlertCircle size={14} aria-hidden className="mt-0.5 shrink-0" />
            <span className="font-mono break-all">{submitError}</span>
          </p>
        )}
      </fieldset>
    </form>
  );
}

function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <label
        htmlFor={id}
        className="flex items-baseline flex-wrap gap-x-3 gap-y-1 font-display text-sm uppercase tracking-[0.06em] text-text-emphasis"
      >
        <span>{label}</span>
        {hint && (
          <span className="text-text-subtle normal-case tracking-normal text-sm font-normal">
            — {hint}
          </span>
        )}
      </label>
      {children}
    </div>
  );
}
