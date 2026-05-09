import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from './api';

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

  it('listSessions: GET /api/sessions', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse([]));
    await api.listSessions();
    expect(fetchSpy).toHaveBeenCalledWith('/api/sessions', expect.any(Object));
  });

  it('startSession: POST /api/sessions with worktree_id', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({ id: 's' }, 201));
    await api.startSession('w1');
    const call = fetchSpy.mock.calls[0]!;
    expect(JSON.parse(call[1].body)).toEqual({ worktree_id: 'w1' });
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
});
