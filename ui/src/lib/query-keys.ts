export const queryKeys = {
  projects: ['projects'] as const,
  worktrees: (projectId: string) => ['worktrees', projectId] as const,
  sessions: ['sessions'] as const,
  tasks: ['tasks'] as const,
  tasksForProject: (projectId: string) => ['tasks', { projectId }] as const,
  task: (taskId: string) => ['tasks', { id: taskId }] as const,
  run: (taskId: string) => ['runs', { taskId }] as const,
  catalog: ['catalog'] as const,
};
