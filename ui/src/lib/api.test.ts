import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { api, type Project, type Repository, type Task, type Worktree } from './api';

type FetchSpy = ReturnType<typeof vi.fn>;

describe('api', () => {
  let fetchSpy: FetchSpy;

  beforeEach(() => {
    fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function jsonResponse(body: unknown, status = 200): Response {
    return new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  it('listProjects: GET /api/projects', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    await api.listProjects();
    expect(fetchSpy).toHaveBeenCalledWith('/api/projects', expect.any(Object));
  });

  it('createProject: POST /api/projects with payload', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 'x' }, 201));
    await api.createProject('foo', '/tmp/foo');
    const call = fetchSpy.mock.calls[0]!;
    expect(call[0]).toBe('/api/projects');
    expect(call[1].method).toBe('POST');
    expect(JSON.parse(call[1].body)).toEqual({ name: 'foo', path: '/tmp/foo' });
  });

  it('deleteProject: DELETE /api/projects/{id} returns void on 204', async () => {
    fetchSpy.mockResolvedValueOnce(new Response(null, { status: 204 }));
    const result = await api.deleteProject('abc');
    expect(result).toBeUndefined();
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/projects/abc',
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('listWorktrees: GET /api/projects/{id}/worktrees', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    await api.listWorktrees('p1');
    expect(fetchSpy).toHaveBeenCalledWith('/api/projects/p1/worktrees', expect.any(Object));
  });

  it('deleteWorktree: DELETE /api/worktrees/{id} returns void on 204', async () => {
    fetchSpy.mockResolvedValueOnce(new Response(null, { status: 204 }));
    const result = await api.deleteWorktree('w1');
    expect(result).toBeUndefined();
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/worktrees/w1',
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('listSessions: GET /api/sessions', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    await api.listSessions();
    expect(fetchSpy).toHaveBeenCalledWith('/api/sessions', expect.any(Object));
  });

  it('startSession: deprecated stub throws synchronously', () => {
    expect(() => api.startSession('w1')).toThrow(/deprecated/i);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('stopSession: POST /api/sessions/{id}/stop returns void on 204', async () => {
    fetchSpy.mockResolvedValueOnce(new Response(null, { status: 204 }));
    const result = await api.stopSession('s1');
    expect(result).toBeUndefined();
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/sessions/s1/stop',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('throws when response is not ok', async () => {
    fetchSpy.mockResolvedValueOnce(new Response('boom', { status: 500 }));
    await expect(api.listProjects()).rejects.toThrow(/HTTP 500/);
  });

  it('listTasks: GET /api/tasks (no filter)', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    await api.listTasks();
    expect(fetchSpy).toHaveBeenCalledWith('/api/tasks', expect.any(Object));
  });

  it('listTasks: GET /api/tasks?project_ids=… when filter provided', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    await api.listTasks(['p1', 'p2']);
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/tasks?project_ids=p1%2Cp2',
      expect.any(Object),
    );
  });

  it('getTask: GET /api/tasks/{id}', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 't1' }));
    await api.getTask('t1');
    expect(fetchSpy).toHaveBeenCalledWith('/api/tasks/t1', expect.any(Object));
  });

  it('createTask: POST /api/tasks with payload', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 't1' }, 201));
    await api.createTask({ project_id: 'p1', title: 'New', description: 'd' });
    const call = fetchSpy.mock.calls[0]!;
    expect(call[0]).toBe('/api/tasks');
    expect(call[1].method).toBe('POST');
    expect(JSON.parse(call[1].body)).toEqual({
      project_id: 'p1',
      title: 'New',
      description: 'd',
    });
  });

  it('createTask: POST /api/tasks accepts optional branch', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 't1' }, 201));
    await api.createTask({ project_id: 'p1', title: 'T', branch: 'feature/foo' });
    const call = fetchSpy.mock.calls[0]!;
    expect(JSON.parse(call[1].body)).toEqual({
      project_id: 'p1',
      title: 'T',
      branch: 'feature/foo',
    });
  });

  it('createTask: POST /api/tasks accepts optional template', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 't1' }, 201));
    await api.createTask({ project_id: 'p1', title: 'T', template: 'frontend' });
    const call = fetchSpy.mock.calls[0]!;
    expect(JSON.parse(call[1].body)).toEqual({
      project_id: 'p1',
      title: 'T',
      template: 'frontend',
    });
  });

  it('getCatalog: GET /api/catalog', async () => {
    const fake = {
      version: '1',
      fallback_permission_profile: 'yolo',
      permission_profiles: [],
      templates: [],
    };
    fetchSpy.mockResolvedValueOnce(jsonResponse(fake));
    const r = await api.getCatalog();
    expect(fetchSpy).toHaveBeenCalledWith('/api/catalog', expect.any(Object));
    expect(r).toEqual(fake);
  });

  it('patchTask: PATCH /api/tasks/{id} with partial body', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 't1' }));
    await api.patchTask('t1', { state: 'ready' });
    const call = fetchSpy.mock.calls[0]!;
    expect(call[0]).toBe('/api/tasks/t1');
    expect(call[1].method).toBe('PATCH');
    expect(JSON.parse(call[1].body)).toEqual({ state: 'ready' });
  });

  it('patchTask: accepts branch field', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 't1' }));
    await api.patchTask('t1', { branch: 'release/v1' });
    const call = fetchSpy.mock.calls[0]!;
    expect(JSON.parse(call[1].body)).toEqual({ branch: 'release/v1' });
  });

  it('startTaskSession: POST /api/tasks/{id}/sessions with empty body', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 's1' }, 201));
    await api.startTaskSession('t1');
    const call = fetchSpy.mock.calls[0]!;
    expect(call[0]).toBe('/api/tasks/t1/sessions');
    expect(call[1].method).toBe('POST');
    expect(JSON.parse(call[1].body)).toEqual({});
  });

  // Type assertions: ensure the F5 type surface compiles. These exist purely
  // for the type-checker; runtime is a no-op `expect(true).toBe(true)`.
  it('types: Project carries repositories[]; Worktree carries F5 fields; Task carries branch', () => {
    const repo: Repository = { id: 'r1', name: 'svc', sub_path: '.' };
    const project: Project = {
      id: 'p1',
      name: 'monorepo',
      path: '/tmp/m',
      created_at: '2026-05-10T00:00:00Z',
      repositories: [repo],
    };
    const worktree: Worktree = {
      id: 'w1',
      repository_id: 'r1',
      repository_name: 'svc',
      task_id: null,
      path: '/tmp/wt',
      branch: 'main',
      is_orphan: false,
    };
    const task: Task = {
      id: 't1',
      project_id: 'p1',
      title: 'T',
      description: '',
      state: 'idea',
      template: null,
      permission_profile: null,
      branch: 'feature/foo',
      created_at: '2026-05-10T00:00:00Z',
      updated_at: '2026-05-10T00:00:00Z',
      active_session_id: null,
    };
    expect([project.repositories[0]?.id, worktree.is_orphan, task.branch]).toEqual([
      repo.id,
      false,
      'feature/foo',
    ]);
  });

  // === F6 — Run from Panel endpoints ========================================

  it('startRun: POST /api/tasks/{id}/runs with empty body', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 'r1' }, 201));
    await api.startRun('t1');
    const call = fetchSpy.mock.calls[0]!;
    expect(call[0]).toBe('/api/tasks/t1/runs');
    expect(call[1].method).toBe('POST');
    expect(JSON.parse(call[1].body)).toEqual({});
  });

  it('getActiveRun: GET /api/tasks/{id}/run', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 'r1', status: 'ready' }));
    const run = await api.getActiveRun('t1');
    expect(fetchSpy).toHaveBeenCalledWith('/api/tasks/t1/run', expect.any(Object));
    expect(run.status).toBe('ready');
  });

  it('stopRun: POST /api/runs/{id}/stop returns void on 204', async () => {
    fetchSpy.mockResolvedValueOnce(new Response(null, { status: 204 }));
    const result = await api.stopRun('r1');
    expect(result).toBeUndefined();
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/runs/r1/stop',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('bootstrapManifest: POST /api/tasks/{id}/bootstrap-manifest', async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ session_id: 'abc', cwd: '/p' }, 202),
    );
    const r = await api.bootstrapManifest('t1');
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/tasks/t1/bootstrap-manifest',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(r.session_id).toBe('abc');
    expect(r.cwd).toBe('/p');
  });

  it('types: Run/ServiceStatus/BootstrapSession compile', () => {
    const svc: import('./api').ServiceStatus = {
      name: 'backend', state: 'ready', port_host: 31101,
      port_container: 8000, container_id: 'cid1', error: null,
    };
    const run: import('./api').Run = {
      id: 'r1', task_id: 't1', cwd: '/c', manifest_path: '/m',
      status: 'ready', services: [svc],
      network_name: 'jarvis-run-abc',
      started_at: '2026-01-01T00:00:00Z', ended_at: null, error_message: null,
    };
    const bs: import('./api').BootstrapSession = { session_id: 'abc', cwd: '/p' };
    expect([run.services[0]?.port_host, bs.cwd]).toEqual([31101, '/p']);
  });
});
