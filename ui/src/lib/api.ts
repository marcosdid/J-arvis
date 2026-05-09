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
  status: string;
  pid: number | null;
  jail_id: string | null;
  started_at: string;
  ended_at: string | null;
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
};
