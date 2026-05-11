export type Repository = {
  id: string;
  name: string;
  sub_path: string;
};

export type Project = {
  id: string;
  name: string;
  path: string;
  created_at: string;
  repositories: Repository[];
};

export type Worktree = {
  id: string;
  repository_id: string;
  repository_name: string;
  task_id: string | null;
  path: string;
  branch: string | null;
  is_orphan: boolean;
};

export type Session = {
  id: string;
  task_id: string;
  cwd: string;
  status: string;
  pid: number | null;
  jail_id: string | null;
  started_at: string;
  ended_at: string | null;
};

export type ServiceStatus = {
  name: string;
  state: 'pending' | 'building' | 'seeding' | 'ready' | 'failed' | 'stopping' | 'stopped';
  port_host: number | null;
  port_container: number | null;
  container_id: string | null;
  error: string | null;
};

export type Run = {
  id: string;
  task_id: string;
  cwd: string;
  manifest_path: string;
  status: 'pending' | 'building' | 'seeding' | 'ready' | 'failed' | 'stopping' | 'stopped';
  services: ServiceStatus[];
  network_name: string;
  started_at: string;
  ended_at: string | null;
  error_message: string | null;
};

export type BootstrapSession = {
  session_id: string;
  cwd: string;
};

export type Task = {
  id: string;
  project_id: string;
  title: string;
  description: string;
  state: string;
  template: string | null;
  permission_profile: string | null;
  branch: string | null;
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
  deleteWorktree: (id: string) =>
    http<void>(`/worktrees/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  listSessions: () => http<Session[]>('/sessions'),
  // Deprecated F1/F4 quick-session endpoint dropped in F5 (decision #5).
  // Kept as a throwing stub so existing UI callers compile until F5.j/F5.k
  // remove the last reference. Calling it at runtime fails fast.
  startSession: (_worktreeId: string): Promise<Session> => {
    throw new Error('api.startSession is deprecated; use startTaskSession (F5)');
  },
  stopSession: (id: string) =>
    http<void>(`/sessions/${encodeURIComponent(id)}/stop`, { method: 'POST' }),
  listTasks: (projectIds?: string[]) => {
    const qs = projectIds?.length
      ? `?project_ids=${encodeURIComponent(projectIds.join(','))}`
      : '';
    return http<Task[]>(`/tasks${qs}`);
  },
  getTask: (id: string) => http<Task>(`/tasks/${encodeURIComponent(id)}`),
  createTask: (input: {
    project_id: string;
    title: string;
    description?: string;
    branch?: string;
  }) => http<Task>('/tasks', { method: 'POST', body: JSON.stringify(input) }),
  patchTask: (
    id: string,
    patch: Partial<Pick<Task, 'title' | 'description' | 'state' | 'branch'>>,
  ) =>
    http<Task>(`/tasks/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),
  startTaskSession: (taskId: string) =>
    http<Session>(`/tasks/${encodeURIComponent(taskId)}/sessions`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  // F6 — Run from Panel
  startRun: (taskId: string) =>
    http<Run>(`/tasks/${encodeURIComponent(taskId)}/runs`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  getActiveRun: (taskId: string) =>
    http<Run>(`/tasks/${encodeURIComponent(taskId)}/run`),
  stopRun: (runId: string) =>
    http<void>(`/runs/${encodeURIComponent(runId)}/stop`, { method: 'POST' }),
  bootstrapManifest: (taskId: string) =>
    http<BootstrapSession>(
      `/tasks/${encodeURIComponent(taskId)}/bootstrap-manifest`,
      { method: 'POST' },
    ),
};
