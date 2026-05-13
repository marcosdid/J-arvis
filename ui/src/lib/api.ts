// F10 native pivot: tasks and projects go through Wails bindings.
// Sessions / runs / worktrees / catalog endpoints are stubbed and throw —
// they will be reimplemented as Wails APIs in F10.3+.

import * as TasksBinding from '../wailsjs/go/api/TasksAPI';
import * as ProjectsBinding from '../wailsjs/go/api/ProjectsAPI';

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

const Tasks = TasksBinding;
const Projects = ProjectsBinding;

function notImplemented(name: string): never {
  throw new Error(
    `${name}: not yet ported to the native backend (planned in F10.3+). ` +
      `If you need this feature, run the legacy Python backend on tag v0.9-python-final.`,
  );
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

  // Stubs — not yet ported in F10 Block A
  listWorktrees: (_projectId: string): Promise<Worktree[]> => notImplemented('listWorktrees'),
  deleteWorktree: (_id: string): Promise<void> => notImplemented('deleteWorktree'),
  listSessions: (): Promise<Session[]> => notImplemented('listSessions'),
  startSession: (_worktreeId: string): Promise<Session> => notImplemented('startSession'),
  stopSession: (_id: string): Promise<void> => notImplemented('stopSession'),
  startTaskSession: (_taskId: string): Promise<Session> => notImplemented('startTaskSession'),
  startRun: (_taskId: string): Promise<Run> => notImplemented('startRun'),
  getActiveRun: (_taskId: string): Promise<Run> => notImplemented('getActiveRun'),
  stopRun: (_runId: string): Promise<void> => notImplemented('stopRun'),
  bootstrapManifest: (_taskId: string): Promise<BootstrapSession> => notImplemented('bootstrapManifest'),
  getCatalog: (): Promise<Catalog> => notImplemented('getCatalog'),
};
