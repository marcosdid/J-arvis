export type Project = {
  id: string;
  name: string;
  path: string;
  created_at: string;
};

export type Worktree = {
  id: string;
  project_id: string;
  path: string;
  branch: string | null;
};

export type Session = {
  id: string;
  worktree_id: string;
  task_id: string;
  status: string;
  pid: number | null;
  jail_id: string | null;
  started_at: string;
  ended_at: string | null;
};

export type Task = {
  id: string;
  project_id: string;
  title: string;
  description: string;
  state: string;
  template: string | null;
  permission_profile: string | null;
  created_at: string;
  updated_at: string;
  active_session_id: string | null;
};

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`HTTP ${response.status}: ${detail}`);
  }
  // Contract: only 204 is allowed to have an empty body. Other 2xx responses
  // must return JSON; otherwise `response.json()` throws SyntaxError.
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  listProjects: () => http<Project[]>('/projects'),
  createProject: (name: string, path: string) =>
    http<Project>('/projects', {
      method: 'POST',
      body: JSON.stringify({ name, path }),
    }),
  deleteProject: (id: string) =>
    http<void>(`/projects/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  listWorktrees: (projectId: string) =>
    http<Worktree[]>(`/projects/${encodeURIComponent(projectId)}/worktrees`),
  listSessions: () => http<Session[]>('/sessions'),
  startSession: (worktreeId: string) =>
    http<Session>('/sessions', {
      method: 'POST',
      body: JSON.stringify({ worktree_id: worktreeId }),
    }),
  stopSession: (id: string) =>
    http<void>(`/sessions/${encodeURIComponent(id)}/stop`, { method: 'POST' }),
  listTasks: (projectIds?: string[]) => {
    const qs = projectIds?.length
      ? `?project_ids=${encodeURIComponent(projectIds.join(','))}`
      : '';
    return http<Task[]>(`/tasks${qs}`);
  },
  getTask: (id: string) => http<Task>(`/tasks/${encodeURIComponent(id)}`),
  createTask: (input: { project_id: string; title: string; description?: string }) =>
    http<Task>('/tasks', { method: 'POST', body: JSON.stringify(input) }),
  patchTask: (id: string, patch: Partial<Pick<Task, 'title' | 'description' | 'state'>>) =>
    http<Task>(`/tasks/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),
  startTaskSession: (taskId: string, worktreeId: string) =>
    http<Session>(`/tasks/${encodeURIComponent(taskId)}/sessions`, {
      method: 'POST',
      body: JSON.stringify({ worktree_id: worktreeId }),
    }),
};
