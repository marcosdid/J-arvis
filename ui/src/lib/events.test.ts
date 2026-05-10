import { describe, expect, it, vi } from 'vitest';
import { dispatch, type WsEvent } from './events';

describe('dispatch', () => {
  it('calls handler matching type', () => {
    const onStatus = vi.fn();
    const event: WsEvent = {
      type: 'session.status', session_id: 'x', task_id: null,
      payload: { status: 'idle', previous: 'executing' }, at: '...',
    };
    dispatch(event, { 'session.status': onStatus });
    expect(onStatus).toHaveBeenCalledWith(event);
  });

  it('does nothing for unknown type', () => {
    const handler = vi.fn();
    // @ts-expect-error testing unknown type at runtime
    dispatch({ type: 'session.unknown', session_id: 'x', payload: {}, at: '' },
             { 'session.status': handler });
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
