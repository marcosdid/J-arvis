// F10 native pivot: tasks and projects go through Wails bindings.
// Sessions / runs / worktrees / catalog endpoints are stubbed and throw —
// they will be reimplemented as Wails APIs in F10.3+.

import * as TasksBinding from '../wailsjs/go/api/TasksAPI';
import * as ProjectsBinding from '../wailsjs/go/api/ProjectsAPI';
import * as WorktreesBinding from '../wailsjs/go/api/WorktreesAPI';
import * as SessionsBinding from '../wailsjs/go/api/SessionsAPI';
import * as CatalogBinding from '../wailsjs/go/api/CatalogAPI';
import * as RunsBinding from '../wailsjs/go/api/RunsAPI';
import * as BootstrapBinding from '../wailsjs/go/api/BootstrapAPI';

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

export type SessionStatus = 'executing' | 'awaiting_response' | 'idle' | 'error' | 'done';

export type Session = {
  id: string;
  task_id: string;
  status: SessionStatus;
  pid: number | null;
  cwd: string;
  last_hook_at: string | null;
  started_at: string;
  ended_at: string | null;
};

export type TranscriptMessage = {
  role: 'user' | 'assistant' | 'tool_use' | 'tool_result';
  content: string;
  tool_name: string | null;
  timestamp: string;
  source_file: string;
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

export type StartRunResult = {
  run: Run | null;
  bootstrap: { reason: string } | null;
};

export type BootstrapSession = {
  session_id: string;
  cwd: string;
  manifest_path: string;
  prompt_path: string;
};

export type PermissionProfile = {
  name: string;
  description: string;
  claude_args: string[];
};

export type Template = {
  name: string;
  description: string;
  default_permission_profile: string;
  branch_prefix: string;
};

export type Catalog = {
  version: '1';
  fallback_permission_profile: string;
  permission_profiles: PermissionProfile[];
  templates: Template[];
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

// Wails-generated `store.Task` and `store.Project` are class types with a
// `convertValues` helper baked in. We project them onto plain-object public
// shapes so consumers don't have to depend on the binding artifact, and we
// map `undefined` to `null` to keep the historical nullable contract.
type StoreTaskShape = {
  id: string;
  project_id: string;
  title: string;
  description: string;
  state: string;
  branch?: string;
  template?: string;
  permission_profile?: string;
  created_at: unknown;
  updated_at: unknown;
  active_session_id?: string;
};

type StoreProjectShape = {
  id: string;
  name: string;
  path: string;
  created_at: unknown;
  repositories: Repository[];
};

function toTask(s: StoreTaskShape): Task {
  return {
    id: s.id,
    project_id: s.project_id,
    title: s.title,
    description: s.description,
    state: s.state,
    branch: s.branch ?? null,
    template: s.template ?? null,
    permission_profile: s.permission_profile ?? null,
    created_at: String(s.created_at ?? ''),
    updated_at: String(s.updated_at ?? ''),
    active_session_id: s.active_session_id ?? null,
  };
}

function toProject(p: StoreProjectShape): Project {
  return {
    id: p.id,
    name: p.name,
    path: p.path,
    created_at: String(p.created_at ?? ''),
    repositories: p.repositories ?? [],
  };
}

// Backend RunView (post-pivot) carries id/task_id/status/cwd/ports/urls/network_name
// plus timestamps. Legacy UI Run shape still expects `services` and `manifest_path`.
// Until the UI is reworked to consume ports/urls directly, project safe defaults so
// existing components/tests keep compiling.
function toRun(v: any): Run {
  return {
    id: v.id,
    task_id: v.task_id,
    cwd: v.cwd,
    manifest_path: '',
    status: v.status,
    services: [],
    network_name: v.network_name,
    started_at: String(v.started_at ?? ''),
    ended_at: v.ended_at != null ? String(v.ended_at) : null,
    error_message: v.error_message ?? null,
  };
}

// Cache the local HTTP base URL on first call. Wails calls are async; cache
// lets subsequent SSE URL builds avoid re-awaiting the binding.
let cachedLocalHTTPBase: string | null = null;
async function getLocalHTTPBase(): Promise<string> {
  if (cachedLocalHTTPBase != null) return cachedLocalHTTPBase;
  cachedLocalHTTPBase = await RunsBinding.LocalHTTPBase();
  return cachedLocalHTTPBase;
}

function toSession(s: any): Session {
  return {
    id: s.id,
    task_id: s.task_id,
    status: s.status,
    pid: s.pid ?? null,
    cwd: s.cwd,
    last_hook_at: s.last_hook_at != null ? String(s.last_hook_at) : null,
    started_at: String(s.started_at ?? ''),
    ended_at: s.ended_at != null ? String(s.ended_at) : null,
  };
}

const Tasks = TasksBinding;
const Projects = ProjectsBinding;

// Stubs return safe-empty values rather than throwing — throwing cascades
// into React Query retry storms that freeze the UI. Real impls land in F10.3+.
function notFound<T>(): Promise<T> {
  // For "get one or 404" hooks: useRun, etc. They expect a thrown HTTP 404
  // to mean "no active run" (it gets translated to null by the hook).
  return Promise.reject(new Error('HTTP 404: not implemented in F10 Block A'));
}

export const api = {
  // Projects (F10.2)
  listProjects: async (): Promise<Project[]> => (await Projects.List()).map(toProject),
  createProject: async (name: string, path: string): Promise<Project> =>
    toProject(await Projects.Create({ name, path })),
  deleteProject: (id: string): Promise<void> => Projects.Delete(id),

  // Tasks (F10.2)
  listTasks: async (projectIds?: string[]): Promise<Task[]> =>
    (await Tasks.List(projectIds ?? [])).map(toTask),
  getTask: async (id: string): Promise<Task> => toTask(await Tasks.Get(id)),
  createTask: async (input: {
    project_id: string;
    title: string;
    description?: string;
    branch?: string;
    template?: string;
  }): Promise<Task> =>
    toTask(
      await Tasks.Create({
        project_id: input.project_id,
        title: input.title,
        description: input.description ?? '',
        ...(input.branch !== undefined ? { branch: input.branch } : {}),
        ...(input.template !== undefined ? { template: input.template } : {}),
      }),
    ),
  patchTask: async (
    id: string,
    patch: Partial<Pick<Task, 'title' | 'description' | 'state' | 'branch'>>,
  ): Promise<Task> => {
    const cleaned: { state?: string; title?: string; description?: string; branch?: string } = {};
    if (patch.title !== undefined) cleaned.title = patch.title;
    if (patch.description !== undefined) cleaned.description = patch.description;
    if (patch.state !== undefined) cleaned.state = patch.state;
    if (patch.branch !== undefined && patch.branch !== null) cleaned.branch = patch.branch;
    return toTask(await Tasks.Patch(id, cleaned));
  },

  // Stubs — F10 Block A; real impls in F10.3+. Return neutral values to
  // avoid retry storms in React Query.
  listWorktrees: async (projectId: string): Promise<Worktree[]> => {
    const rows = await WorktreesBinding.ListByProject(projectId);
    return (rows ?? []).map(
      (w: any): Worktree => ({
        id: w.id,
        repository_id: w.repository_id,
        repository_name: w.repository_name,
        task_id: w.task_id ?? null,
        path: w.path,
        branch: w.branch ?? null,
        is_orphan: w.is_orphan,
      }),
    );
  },
  deleteWorktree: (id: string): Promise<void> => WorktreesBinding.Delete(id).then(() => undefined),

  // Sessions (F10.4)
  startSession: (taskId: string): Promise<Session> =>
    SessionsBinding.Start(taskId).then((s: any) => toSession(s)),
  stopSession: (id: string): Promise<void> => SessionsBinding.Stop(id).then(() => undefined),
  listSessions: (taskId: string): Promise<Session[]> =>
    SessionsBinding.ListByTask(taskId).then((rows: any[]) => (rows ?? []).map(toSession)),
  getTranscript: (sessionId: string): Promise<TranscriptMessage[]> =>
    SessionsBinding.GetTranscript(sessionId).then((rows: any[]) =>
      (rows ?? []).map((m: any) => ({
        role: m.role,
        content: m.content,
        tool_name: m.tool_name ?? null,
        timestamp: String(m.timestamp ?? ''),
        source_file: m.source_file ?? '',
      })),
    ),
  startTaskSession: (_taskId: string): Promise<Session> => notFound<Session>(),
  startRun: async (taskId: string): Promise<StartRunResult> => {
    const raw = await RunsBinding.Start(taskId);
    return {
      run: raw.run != null ? toRun(raw.run) : null,
      bootstrap: raw.bootstrap != null ? { reason: raw.bootstrap.reason } : null,
    };
  },
  getActiveRun: async (taskId: string): Promise<Run> => {
    // Backend returns ErrNotFound when nenhuma run ativa; Wails surfaces isso
    // como Error com mensagem. Hook useRun espera `HTTP 404` prefix pra mapear
    // pra null — normalize aqui.
    try {
      return toRun(await RunsBinding.Get(taskId));
    } catch (err) {
      const msg = (err as Error)?.message ?? '';
      if (/not\s*found/i.test(msg) || msg.toLowerCase().includes('no active run')) {
        throw new Error('HTTP 404: no active run');
      }
      throw err;
    }
  },
  stopRun: (runId: string): Promise<void> => RunsBinding.Stop(runId).then(() => undefined),
  getRunLogsEventSourceURL: async (runId: string, service: string): Promise<string> => {
    const base = await getLocalHTTPBase();
    return `${base}/api/runs/${encodeURIComponent(runId)}/logs?service=${encodeURIComponent(service)}`;
  },
  bootstrapManifest: async (taskId: string): Promise<BootstrapSession> => {
    const v = await BootstrapBinding.Start(taskId);
    return {
      session_id: v.session_id,
      cwd: v.cwd,
      manifest_path: v.manifest_path,
      prompt_path: v.prompt_path,
    };
  },
  cancelBootstrap: (taskId: string): Promise<void> => BootstrapBinding.Cancel(taskId),
  getCatalog: async (): Promise<Catalog> => {
    const v = await CatalogBinding.Get();
    return {
      version: '1',
      fallback_permission_profile: v.fallback_permission_profile,
      permission_profiles: v.permission_profiles ?? [],
      templates: (v.templates ?? []).map((t) => ({
        name: t.name,
        description: t.description,
        default_permission_profile: t.default_permission_profile,
        branch_prefix: t.branch_prefix,
      })),
    };
  },
};
