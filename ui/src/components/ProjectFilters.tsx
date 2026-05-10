import type { Project } from '../lib/api';

type Props = {
  projects: Project[];
  active: string[];
  onChange: (next: string[]) => void;
};

export function ProjectFilters({ projects, active, onChange }: Props) {
  const set = new Set(active);
  return (
    <div className="project-filters">
      {projects.map((p) => {
        const on = set.has(p.id);
        return (
          <button
            key={p.id}
            type="button"
            className={on ? 'chip active' : 'chip'}
            onClick={() =>
              onChange(on ? active.filter((x) => x !== p.id) : [...active, p.id])
            }
          >
            {p.name}
          </button>
        );
      })}
    </div>
  );
}
