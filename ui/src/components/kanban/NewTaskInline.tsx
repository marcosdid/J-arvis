import { useState } from 'react';
import { useCreateTask } from '../../hooks/useTaskMutations';

type Props = {
  columnState: string;
  projectId: string;
};

export function NewTaskInline({ columnState: _columnState, projectId }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [title, setTitle] = useState('');
  const create = useCreateTask();

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
          },
          {
            onSuccess: () => {
              setTitle('');
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
          }
        }}
        placeholder="task title (Enter to create)"
        className="bg-bg-deep border border-border-subtle text-text-emphasis text-xs px-2 py-1 rounded-sm transition-colors duration-[180ms] ease-out focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/40"
      />
    </form>
  );
}
