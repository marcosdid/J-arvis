import { Button } from '@/components/ui/button';
import { useKeyboardShortcut } from '@/hooks/useKeyboardShortcut';
import { BrandMark } from './BrandMark';

type Props = {
  projectsCount: number;
  tasksCount: number;
  activeCount: number;
  onFilter?: () => void;
  onToggleProjects?: () => void;
  onNewTask?: () => void;
};

export function AppHeader({
  projectsCount,
  tasksCount,
  activeCount,
  onFilter,
  onToggleProjects,
  onNewTask,
}: Props) {
  useKeyboardShortcut('/', () => onFilter?.());
  useKeyboardShortcut('p', () => onToggleProjects?.());
  useKeyboardShortcut('n', () => onNewTask?.());
  useKeyboardShortcut('r', () => {/* no-op — F9+1 RunPanel placeholder */});

  return (
    <header className="flex justify-between items-center px-4 py-3 border-b border-border-subtle bg-bg-deep">
      <div className="flex items-center gap-3">
        <BrandMark />
        <div className="text-text-subtle text-[0.7rem] tracking-wide border-l border-border-subtle pl-3">
          <span className="text-accent-primary font-semibold">{projectsCount}</span> proj
          <span className="mx-1">·</span>
          <span className="text-accent-primary font-semibold">{tasksCount}</span> tsk
          <span className="mx-1">·</span>
          <span className="text-accent-primary font-semibold">{activeCount}</span> active
        </div>
      </div>
      <div className="flex gap-1.5 items-center">
        <Button variant="outline" size="sm" onClick={onFilter}>
          <span className="text-accent-primary font-bold mr-1">[/]</span>filter
        </Button>
        <Button variant="outline" size="sm" onClick={onToggleProjects}>
          <span className="text-accent-primary font-bold mr-1">[p]</span>projects
        </Button>
        <Button variant="outline" size="sm" disabled title="F9+1">
          <span className="text-accent-primary font-bold mr-1">[r]</span>run
        </Button>
        <Button variant="default" size="sm" onClick={onNewTask}>
          <span className="font-bold mr-1">[n]</span>new task
        </Button>
      </div>
    </header>
  );
}
