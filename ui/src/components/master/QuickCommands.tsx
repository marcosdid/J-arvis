interface QuickCommandsProps {
  onInject: (command: string) => void;
}

const CHIPS: { label: string; command: string }[] = [
  { label: 'list tasks', command: 'j-arvis list_tasks' },
  { label: 'create task', command: 'j-arvis create_task ' },
  { label: 'update state', command: 'j-arvis update_state ' },
  { label: 'discard', command: 'j-arvis discard ' },
  { label: 'show doing', command: 'j-arvis list_tasks state=in_progress' },
];

export function QuickCommands({ onInject }: QuickCommandsProps) {
  return (
    <div className="flex gap-1.5 px-3 py-1.5 border-b border-border-subtle bg-bg-surface overflow-x-auto">
      {CHIPS.map(({ label, command }) => (
        <button
          key={label}
          type="button"
          onClick={() => onInject(command)}
          className="text-[0.65rem] px-2 py-0.5 bg-bg-elevated border border-border-subtle rounded-sm hover:border-accent-primary text-text-subtle hover:text-accent-primary transition-colors whitespace-nowrap"
        >
          {label}
        </button>
      ))}
    </div>
  );
}
