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
    onEvent({ type: 'session.status', session_id: 'x', payload: { status: 'idle', previous: 'executing' }, at: '' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.sessions });
  });

  it('invalidates on session.stopped too', () => {
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useSessionEvents(qc));
    const onEvent = connectMock.mock.calls[0]?.[0] as (e: unknown) => void;
    onEvent({ type: 'session.stopped', session_id: 'x', payload: {}, at: '' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.sessions });
  });
});
