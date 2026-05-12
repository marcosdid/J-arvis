import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';

import { api } from './lib/api';
import { loadFilters, saveFilters } from './lib/kanbanFilters';
import { queryKeys } from './lib/query-keys';
import { useSessionEvents } from './hooks/useSessionEvents';

import { AppShell } from './app/AppShell';
import { Kanban } from './components/kanban/Kanban';
import { MasterSidebar } from './components/MasterSidebar';
import { NewTaskForm } from './components/NewTaskForm';
import { ProjectFilters } from './components/ProjectFilters';
import { ProjectsDrawer } from './components/ProjectsDrawer';
import { TaskDetailModal } from './components/TaskDetailModal';

export function App() {
  const queryClient = useQueryClient();
  useSessionEvents(queryClient);

  const projects = useQuery({
    queryKey: queryKeys.projects,
    queryFn: api.listProjects,
  });

  const tasks = useQuery({
    queryKey: queryKeys.tasks,
    queryFn: () => api.listTasks(),
  });

  const knownIds = useMemo(
    () => new Set((projects.data ?? []).map((p) => p.id)),
    [projects.data],
  );
  const [filters, setFilters] = useState<string[]>(() => loadFilters());

  useEffect(() => {
    saveFilters(filters);
  }, [filters]);

  // Drop ids of deleted projects when the projects list changes
  useEffect(() => {
    if (!projects.data) return;
    setFilters((prev) => prev.filter((id) => knownIds.has(id)));
  }, [knownIds, projects.data]);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const projectsCount = projects.data?.length ?? 0;
  const tasksCount = tasks.data?.length ?? 0;
  const activeCount = (tasks.data ?? []).filter((t) => t.state === 'in_progress').length;

  return (
    <div className="grid grid-cols-[1fr_400px] h-screen overflow-hidden">
      <AppShell
        projectsCount={projectsCount}
        tasksCount={tasksCount}
        activeCount={activeCount}
        wsRtt={null}
        onToggleProjects={() => setDrawerOpen(true)}
        onNewTask={() => { /* placeholder — Phase 11 wires NewTaskSheet */ }}
        onFilter={() => { /* placeholder — Phase 13 wires filter */ }}
      >
        <ProjectFilters
          projects={projects.data ?? []}
          active={filters}
          onChange={setFilters}
        />
        <Kanban filters={filters} onCardClick={setSelectedTaskId} />
        <NewTaskForm projects={projects.data ?? []} />

        <ProjectsDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
        {selectedTaskId && (
          <TaskDetailModal
            taskId={selectedTaskId}
            onClose={() => setSelectedTaskId(null)}
          />
        )}
      </AppShell>
      <MasterSidebar />
    </div>
  );
}
