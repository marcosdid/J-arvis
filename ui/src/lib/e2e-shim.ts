// E2E shim: when running in a regular browser (not Wails webview),
// install a polyfill on window.go that fetches the e2e HTTP server.
// Activated by query param `?e2e=1&e2ePort=NNNN`.
//
// This is the only file that knows about the HTTP transport — the rest
// of the UI stays Wails-bindings-shaped.

type AnyFn = (...args: unknown[]) => unknown;

declare global {
  interface Window {
    go?: Record<string, Record<string, Record<string, AnyFn>>>;
    runtime?: {
      EventsOn?: (name: string, cb: (payload: unknown) => void) => void;
      EventsOff?: (name: string) => void;
      EventsEmit?: (name: string, payload?: unknown) => void;
      EventsOnMultiple?: (
        name: string,
        cb: (payload: unknown) => void,
        max: number,
      ) => void;
    };
  }
}

function postJson<T>(url: string, body: unknown): Promise<T> {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  }).then(async (res) => {
    if (res.status === 204) return undefined as T;
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}: ${text}`);
    }
    return (await res.json()) as T;
  });
}

export function installE2EShim(): void {
  if (typeof window === 'undefined') return;
  const params = new URLSearchParams(window.location.search);
  const enabled = params.get('e2e') === '1';
  if (!enabled) return;
  const port = params.get('e2ePort') ?? '8088';
  const base = `http://127.0.0.1:${port}`;

  const tasksAPI = {
    List: (projectIds: string[] = []) =>
      postJson(`${base}/e2e/tasks/list`, { project_ids: projectIds }),
    Create: (input: unknown) => postJson(`${base}/e2e/tasks/create`, input),
    Patch: (id: string, patch: unknown) =>
      postJson(`${base}/e2e/tasks/patch`, { id, patch }),
    Get: (id: string) => postJson(`${base}/e2e/tasks/get`, { id }),
    Discard: (id: string) => postJson(`${base}/e2e/tasks/discard`, { id }),
  } as unknown as Record<string, AnyFn>;

  const projectsAPI = {
    List: () => postJson(`${base}/e2e/projects/list`, {}),
    Create: (input: unknown) => postJson(`${base}/e2e/projects/create`, input),
    Delete: (id: string) => postJson(`${base}/e2e/projects/delete`, { id }),
  } as unknown as Record<string, AnyFn>;

  const masterAPI = {
    Start: () => postJson(`${base}/e2e/master/status`, {}),
    Status: () => postJson(`${base}/e2e/master/status`, {}),
    Send: () => Promise.resolve(),
    Resize: () => Promise.resolve(),
    Stop: () => Promise.resolve(),
  } as unknown as Record<string, AnyFn>;

  const healthAPI = {
    Snapshot: () =>
      Promise.resolve({
        appVersion: '0.10.0-e2e',
        uptime: 0,
        sandbox_available: true,
        sandbox_reason: '',
      }),
  } as unknown as Record<string, AnyFn>;

  const worktreesAPI = {
    ListByProject: (projectId: string) =>
      postJson(`${base}/e2e/worktrees/list_by_project`, { project_id: projectId }),
    Delete: (id: string) => postJson(`${base}/e2e/worktrees/delete`, { id }),
  } as unknown as Record<string, AnyFn>;

  const sessionsAPI = {
    Start: (taskId: string) => postJson(`${base}/e2e/sessions/start`, { task_id: taskId }),
    Stop: (id: string) => postJson(`${base}/e2e/sessions/stop`, { id }),
    ListByTask: (taskId: string) =>
      postJson(`${base}/e2e/sessions/list_by_task`, { task_id: taskId }),
    GetTranscript: (id: string) => postJson(`${base}/e2e/sessions/transcript`, { id }),
  } as unknown as Record<string, AnyFn>;

  window.go = {
    api: {
      TasksAPI: tasksAPI,
      ProjectsAPI: projectsAPI,
      MasterAPI: masterAPI,
      HealthAPI: healthAPI,
      WorktreesAPI: worktreesAPI,
      SessionsAPI: sessionsAPI,
    },
  };

  // Minimal runtime stub — no event source yet; tests just verify state
  // via list/get rather than waiting on push events.
  const listeners = new Map<string, Set<(p: unknown) => void>>();
  window.runtime = {
    EventsOn: (name, cb) => {
      const set = listeners.get(name) ?? new Set();
      set.add(cb);
      listeners.set(name, set);
    },
    EventsOff: (name) => {
      listeners.delete(name);
    },
    EventsEmit: (name, payload) => {
      listeners.get(name)?.forEach((cb) => cb(payload));
    },
    EventsOnMultiple: (name, cb, _max) => {
      const set = listeners.get(name) ?? new Set();
      set.add(cb);
      listeners.set(name, set);
    },
  };
}
