import { QueryClient } from '@tanstack/react-query';
import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { queryKeys } from '../lib/query-keys';
import { useSessionEvents } from './useSessionEvents';

const connectMock = vi.fn();
vi.mock('../lib/ws', () => ({
  connectWs: (onEvent: (e: unknown) => void) => {
    connectMock(onEvent);
    return { disconnect: vi.fn() };
  },
}));

beforeEach(() => connectMock.mockReset());

describe('useSessionEvents', () => {
  it('invalidates sessions queries on session.status_changed', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({ type: 'session.status_changed', session_id: 'x', task_id: null, payload: { previous: 'executing', current: 'idle' }, at: '' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.sessions });
  });

  it('invalidates tasks queries on session.status_changed', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({ type: 'session.status_changed', session_id: 'x', task_id: null, payload: { previous: 'executing', current: 'idle' }, at: '' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.tasks });
  });

  it('invalidates sessions queries on session.started', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({ type: 'session.started', session_id: 'x', task_id: 't1', payload: {}, at: '' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.sessions });
  });

  it('invalidates transcript(session_id) on session.tool_use', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({ type: 'session.tool_use', session_id: 'sess-9', task_id: null, payload: { tool: 'Bash' }, at: '' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.transcript('sess-9') });
  });

  it('invalidates on session.stopped too', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({ type: 'session.stopped', session_id: 'x', task_id: null, payload: {}, at: '' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.sessions });
  });

  it('invalidates tasks queries on session.stopped', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({ type: 'session.stopped', session_id: 'x', task_id: null, payload: {}, at: '' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.tasks });
  });

  it('invalidates tasks queries on task.created', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({ type: 'task.created', session_id: '', task_id: 'abc', payload: { project_id: 'p1', title: 'T', state: 'backlog' }, at: '' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.tasks });
  });

  it('invalidates tasks queries on task.updated', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({ type: 'task.updated', session_id: '', task_id: 'abc', payload: { project_id: 'p1', title: 'T', state: 'doing', previous_state: 'backlog' }, at: '' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.tasks });
  });

  it('invalidates worktrees(project_id) on worktree.created', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({
      type: 'worktree.created', session_id: '', task_id: 't1',
      payload: {
        project_id: 'p1', repository_id: 'r1',
        worktree_id: 'w1', path: '/wt', branch: 'feat/x',
      },
      at: '',
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.worktrees('p1') });
  });

  it('invalidates worktrees(project_id) on worktree.removed', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({
      type: 'worktree.removed', session_id: '', task_id: 't1',
      payload: { project_id: 'p1', worktree_id: 'w1', path: '/wt' },
      at: '',
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.worktrees('p1') });
  });

  it('invalidates worktrees(project_id) AND fires emitToast on worktree.orphaned', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    const emitToast = vi.fn();
    renderHook(() => useSessionEvents(qc, emitToast));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({
      type: 'worktree.orphaned', session_id: '', task_id: null,
      payload: {
        project_id: 'p1', worktree_id: 'w1',
        path: '/wt/abandoned', reason: 'fs_missing',
      },
      at: '',
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.worktrees('p1') });
    expect(emitToast).toHaveBeenCalledWith(
      'Worktree não pôde ser removida: /wt/abandoned',
    );
  });

  it('worktree.orphaned without emitToast: invalidates only, no error', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    expect(() => {
      onEvent({
        type: 'worktree.orphaned', session_id: '', task_id: null,
        payload: {
          project_id: 'p1', worktree_id: 'w1',
          path: '/wt', reason: 'fs_missing',
        },
        at: '',
      });
    }).not.toThrow();
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.worktrees('p1') });
  });

  it('run.status invalidates queryKeys.run(task_id)', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({
      type: 'run.status', session_id: '', task_id: 't1',
      payload: { run_id: 'r1', status: 'ready', services: [] }, at: '',
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.run('t1') });
  });

  it('run.failed invalidates + emits toast with service name', () => {
    const qc = new QueryClient();
    const toast = vi.fn();
    renderHook(() => useSessionEvents(qc, toast));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({
      type: 'run.failed', session_id: '', task_id: 't1',
      payload: { run_id: 'r1', service: 'backend', error: 'oops' }, at: '',
    });
    expect(toast).toHaveBeenCalledWith('Run falhou (backend): oops');
  });

  it('run.failed without service emits toast without parens', () => {
    const qc = new QueryClient();
    const toast = vi.fn();
    renderHook(() => useSessionEvents(qc, toast));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({
      type: 'run.failed', session_id: '', task_id: 't1',
      payload: { run_id: 'r1', service: null, error: 'network create failed' }, at: '',
    });
    expect(toast).toHaveBeenCalledWith('Run falhou: network create failed');
  });

  it('run.failed without emitToast just invalidates', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    expect(() => {
      onEvent({
        type: 'run.failed', session_id: '', task_id: 't1',
        payload: { run_id: 'r1', service: null, error: 'x' }, at: '',
      });
    }).not.toThrow();
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.run('t1') });
  });

  it('run.stopped invalidates queryKeys.run(task_id)', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({
      type: 'run.stopped', session_id: '', task_id: 't1',
      payload: { run_id: 'r1', reason: 'manual' }, at: '',
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.run('t1') });
  });

  it('bootstrap.proposed emits toast about manifest ready', () => {
    const qc = new QueryClient();
    const toast = vi.fn();
    renderHook(() => useSessionEvents(qc, toast));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({
      type: 'bootstrap.proposed', session_id: '', task_id: null,
      payload: { manifest_text: 'version: "1"' }, at: '',
    });
    expect(toast).toHaveBeenCalledWith('Manifesto pronto. Tente Run de novo.');
  });

  it('bootstrap.proposed without emitToast is no-op', () => {
    const qc = new QueryClient();
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    expect(() => {
      onEvent({
        type: 'bootstrap.proposed', session_id: '', task_id: null,
        payload: { manifest_text: '' }, at: '',
      });
    }).not.toThrow();
  });
});
