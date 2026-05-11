import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useRunLogs } from './useRunLogs';

type Listener = (line: { service: string; stream: 'stdout'|'stderr'; text: string }) => void;

let lastListener: Listener | null = null;
let lastClose: ReturnType<typeof vi.fn> = vi.fn();

vi.mock('../lib/runSseClient', () => ({
  createLogsSse: vi.fn((_runId: string, _service: string, onLine: Listener) => {
    lastListener = onLine;
    lastClose = vi.fn();
    return { close: lastClose };
  }),
}));

import { createLogsSse } from '../lib/runSseClient';

describe('useRunLogs', () => {
  beforeEach(() => {
    (createLogsSse as ReturnType<typeof vi.fn>).mockClear();
    lastListener = null;
  });
  afterEach(() => vi.clearAllMocks());

  it('does not subscribe when runId or service is null', () => {
    const { result } = renderHook(() => useRunLogs(null, 'a'));
    expect(result.current).toEqual([]);
    expect(createLogsSse).not.toHaveBeenCalled();
  });

  it('does not subscribe when service is null', () => {
    const { result } = renderHook(() => useRunLogs('r1', null));
    expect(result.current).toEqual([]);
    expect(createLogsSse).not.toHaveBeenCalled();
  });

  it('subscribes and accumulates lines', () => {
    const { result } = renderHook(() => useRunLogs('r1', 'svc'));
    expect(createLogsSse).toHaveBeenCalledWith('r1', 'svc', expect.any(Function));
    act(() => {
      lastListener!({ service: 'svc', stream: 'stdout', text: 'line 1' });
      lastListener!({ service: 'svc', stream: 'stderr', text: 'warn' });
    });
    expect(result.current).toEqual([
      { service: 'svc', stream: 'stdout', text: 'line 1' },
      { service: 'svc', stream: 'stderr', text: 'warn' },
    ]);
  });

  it('trims buffer at BUFFER_MAX (500 lines, ring) keeping latest', () => {
    const { result } = renderHook(() => useRunLogs('r1', 'svc'));
    act(() => {
      for (let i = 0; i < 600; i += 1) {
        lastListener!({ service: 'svc', stream: 'stdout', text: `l${i}` });
      }
    });
    expect(result.current).toHaveLength(500);
    expect(result.current[0]!.text).toBe('l100');
    expect(result.current[499]!.text).toBe('l599');
  });

  it('closes connection when runId changes', () => {
    const { rerender } = renderHook(
      ({ id, svc }: { id: string | null; svc: string | null }) => useRunLogs(id, svc),
      { initialProps: { id: 'r1' as string | null, svc: 'svc' as string | null } },
    );
    const firstClose = lastClose;
    rerender({ id: 'r2', svc: 'svc' });
    expect(firstClose).toHaveBeenCalled();
  });

  it('clears lines when switching to null runId', () => {
    const { result, rerender } = renderHook(
      ({ id, svc }: { id: string | null; svc: string | null }) => useRunLogs(id, svc),
      { initialProps: { id: 'r1' as string | null, svc: 'svc' as string | null } },
    );
    act(() => {
      lastListener!({ service: 'svc', stream: 'stdout', text: 'line' });
    });
    expect(result.current).toHaveLength(1);
    rerender({ id: null, svc: 'svc' });
    expect(result.current).toEqual([]);
  });
});
