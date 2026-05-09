export const queryKeys = {
  projects: ['projects'] as const,
  worktrees: (projectId: string) => ['worktrees', projectId] as const,
  sessions: ['sessions'] as const,
};
