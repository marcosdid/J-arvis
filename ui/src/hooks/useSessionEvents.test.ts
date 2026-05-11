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
  it('invalidates sessions queries on session.status', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({ type: 'session.status', session_id: 'x', task_id: null, payload: { status: 'idle', previous: 'executing' }, at: '' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.sessions });
  });

  it('invalidates tasks queries on session.status', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({ type: 'session.status', session_id: 'x', task_id: null, payload: { status: 'idle', previous: 'executing' }, at: '' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.tasks });
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
});
