import { useState } from 'react';
import { useCreateTask } from '../../hooks/useTaskMutations';
import { useCatalog } from '../../hooks/useCatalog';

type Props = {
  columnState: string;
  projectId: string;
};

export function NewTaskInline({ columnState: _columnState, projectId }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [title, setTitle] = useState('');
  const [template, setTemplate] = useState<string>('');
  const create = useCreateTask();
  const catalog = useCatalog();

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        className="w-full text-left text-xs text-text-faint hover:text-accent-primary px-2 py-1 border border-dashed border-border-subtle rounded-sm hover:border-accent-primary transition-colors duration-[180ms] ease-out focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-primary/40"
      >
        + add task
      </button>
    );
  }

  const templates = catalog.data?.templates ?? [];

  return (
    <form
      aria-label="new-task-inline"
      onSubmit={(e) => {
        e.preventDefault();
        if (!title.trim()) return;
        create.mutate(
          {
            title,
            project_id: projectId,
            // Only include `template` when explicitly chosen — keeps the
            // payload identical to pre-F10.5 for the no-template case.
            ...(template ? { template } : {}),
          },
          {
            onSuccess: () => {
              setTitle('');
              setTemplate('');
              setExpanded(false);
            },
          },
        );
      }}
      className="flex flex-col gap-1"
    >
      <input
        autoFocus
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            setExpanded(false);
            setTitle('');
            setTemplate('');
          }
        }}
        placeholder="task title (Enter to create)"
        className="bg-bg-deep border border-border-subtle text-text-emphasis text-xs px-2 py-1 rounded-sm transition-colors duration-[180ms] ease-out focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/40"
      />
      {templates.length > 0 && (
        <select
          aria-label="task-template"
          value={template}
          onChange={(e) => setTemplate(e.target.value)}
          className="bg-bg-deep border border-border-subtle text-text-emphasis text-xs px-2 py-1 rounded-sm transition-colors duration-[180ms] ease-out focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/40"
        >
          <option value="">no template</option>
          {templates.map((t) => (
            <option key={t.name} value={t.name}>
              {t.name}
            </option>
          ))}
        </select>
      )}
    </form>
  );
}
