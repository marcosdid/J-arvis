import { describe, expect, it, vi } from 'vitest';
import { dispatch, type WsEvent } from './events';

describe('dispatch', () => {
  it('calls handler matching type', () => {
    const onStatus = vi.fn();
    const event: WsEvent = {
      type: 'session.status', session_id: 'x',
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
