import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { queryKeys } from '../lib/query-keys';
import {
  useBootstrapManifest,
  useRun,
  useStartRun,
  useStopRun,
} from './useRun';

vi.mock('../lib/api', () => ({
  api: {
    getActiveRun: vi.fn(),
    startRun: vi.fn(),
    stopRun: vi.fn(),
    bootstrapManifest: vi.fn(),
  },
}));

import { api } from '../lib/api';

function makeWrapper(qc: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe('useRun', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.clearAllMocks());

  it('returns the active run when API succeeds', async () => {
    const run = { id: 'r1', task_id: 't1', status: 'ready' };
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockResolvedValue(run);
    const qc = new QueryClient();
    const { result } = renderHook(() => useRun('t1'), { wrapper: makeWrapper(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(run);
  });

  it('returns null when API throws HTTP 404 (no active run)', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('HTTP 404: no active run'),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useRun('t1'), { wrapper: makeWrapper(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
  });

  it('propagates non-404 errors', async () => {
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('HTTP 500: server boom'),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useRun('t1'), { wrapper: makeWrapper(qc) });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it('treats non-Error throws as non-404 (re-throws)', async () => {
    // Branch coverage: `(err as Error).message ?? ''` quando err não tem
    // .message — o `??` fallback dispara, msg vira '', `.startsWith('HTTP 404')`
    // é false, re-throw.
    (api.getActiveRun as ReturnType<typeof vi.fn>).mockImplementation(() => {
      throw { weird: true };
    });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useRun('t1'), { wrapper: makeWrapper(qc) });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe('useStartRun', () => {
  it('calls api.startRun and invalidates run query on success', async () => {
    (api.startRun as ReturnType<typeof vi.fn>).mockResolvedValue({ id: 'r1' });
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, 'invalidateQueries');
    const { result } = renderHook(() => useStartRun('t1'), {
      wrapper: makeWrapper(qc),
    });
    await act(async () => {
      await result.current.mutateAsync();
    });
    expect(api.startRun).toHaveBeenCalledWith('t1');
    expect(spy).toHaveBeenCalledWith({ queryKey: queryKeys.run('t1') });
  });
});

describe('useStopRun', () => {
  it('calls api.stopRun with given run_id and invalidates', async () => {
    (api.stopRun as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, 'invalidateQueries');
    const { result } = renderHook(() => useStopRun('t1'), {
      wrapper: makeWrapper(qc),
    });
    await act(async () => {
      await result.current.mutateAsync('r1');
    });
    expect(api.stopRun).toHaveBeenCalledWith('r1');
    expect(spy).toHaveBeenCalledWith({ queryKey: queryKeys.run('t1') });
  });
});

describe('useBootstrapManifest', () => {
  it('calls api.bootstrapManifest', async () => {
    (api.bootstrapManifest as ReturnType<typeof vi.fn>).mockResolvedValue({
      session_id: 'abc',
      cwd: '/p',
    });
    const qc = new QueryClient();
    const { result } = renderHook(() => useBootstrapManifest('t1'), {
      wrapper: makeWrapper(qc),
    });
    await act(async () => {
      await result.current.mutateAsync();
    });
    expect(api.bootstrapManifest).toHaveBeenCalledWith('t1');
  });
});
