import { describe, expect, it, vi } from 'vitest';
import { dispatch, type WsEvent } from './events';

describe('dispatch', () => {
  it('calls handler matching type', () => {
    const onStatus = vi.fn();
    const event: WsEvent = {
      type: 'session.status_changed', session_id: 'x', task_id: null,
      payload: { previous: 'executing', current: 'idle' }, at: '...',
    };
    dispatch(event, { 'session.status_changed': onStatus });
    expect(onStatus).toHaveBeenCalledWith(event);
  });

  it('does nothing for unknown type', () => {
    const handler = vi.fn();
    // @ts-expect-error testing unknown type at runtime
    dispatch({ type: 'session.unknown', session_id: 'x', payload: {}, at: '' },
             { 'session.status_changed': handler });
    expect(handler).not.toHaveBeenCalled();
  });
});

describe('dispatch — task events', () => {
  it('dispatches task.created', () => {
    const calls: WsEvent[] = [];
    dispatch(
      {
        type: 'task.created', session_id: '', task_id: 't1',
        payload: { project_id: 'p', title: 'T', state: 'idea' },
        at: '2026',
      },
      { 'task.created': (e) => calls.push(e) },
    );
    expect(calls).toHaveLength(1);
  });

  it('dispatches task.updated', () => {
    const calls: WsEvent[] = [];
    dispatch(
      {
        type: 'task.updated', session_id: '', task_id: 't1',
        payload: {
          project_id: 'p', title: 'T',
          state: 'ready', previous_state: 'idea',
        },
        at: '2026',
      },
      { 'task.updated': (e) => calls.push(e) },
    );
    expect(calls).toHaveLength(1);
  });
});

describe('dispatch — worktree events', () => {
  it('dispatches worktree.created', () => {
    const calls: WsEvent[] = [];
    dispatch(
      {
        type: 'worktree.created', session_id: '', task_id: 't1',
        payload: {
          project_id: 'p1', repository_id: 'r1',
          worktree_id: 'w1', path: '/wt', branch: 'feat/x',
        },
        at: '2026',
      },
      { 'worktree.created': (e) => calls.push(e) },
    );
    expect(calls).toHaveLength(1);
  });

  it('dispatches worktree.removed', () => {
    const calls: WsEvent[] = [];
    dispatch(
      {
        type: 'worktree.removed', session_id: '', task_id: 't1',
        payload: { project_id: 'p1', worktree_id: 'w1', path: '/wt' },
        at: '2026',
      },
      { 'worktree.removed': (e) => calls.push(e) },
    );
    expect(calls).toHaveLength(1);
  });

  it('dispatches worktree.orphaned', () => {
    const calls: WsEvent[] = [];
    dispatch(
      {
        type: 'worktree.orphaned', session_id: '', task_id: null,
        payload: {
          project_id: 'p1', worktree_id: 'w1',
          path: '/wt', reason: 'fs_missing',
        },
        at: '2026',
      },
      { 'worktree.orphaned': (e) => calls.push(e) },
    );
    expect(calls).toHaveLength(1);
  });
});
