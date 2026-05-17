import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { queryKeys } from '../lib/query-keys';
import {
  useBootstrapManifest,
  useCancelBootstrap,
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
    cancelBootstrap: vi.fn(),
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
    (api.startRun as ReturnType<typeof vi.fn>).mockResolvedValue({
      run: { id: 'r1', task_id: 't1', status: 'ready' },
      bootstrap: null,
    });
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

  it('surfaces bootstrap hint when manifest missing', async () => {
    (api.startRun as ReturnType<typeof vi.fn>).mockResolvedValue({
      run: null,
      bootstrap: { reason: 'manifest_missing' },
    });
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, 'invalidateQueries');
    const { result } = renderHook(() => useStartRun('t1'), {
      wrapper: makeWrapper(qc),
    });
    let resolved: Awaited<ReturnType<typeof result.current.mutateAsync>> | undefined;
    await act(async () => {
      resolved = await result.current.mutateAsync();
    });
    expect(resolved?.run).toBeNull();
    expect(resolved?.bootstrap?.reason).toBe('manifest_missing');
    expect(spy).not.toHaveBeenCalled();
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
      session_id: 's-1',
      cwd: '/tmp/wt',
      manifest_path: '/tmp/wt/.orchestrator/run.yml',
      prompt_path: '/tmp/wt/.orchestrator/BOOTSTRAP_PROMPT.md',
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

describe('useCancelBootstrap', () => {
  it('calls api.cancelBootstrap with the task id', async () => {
    (api.cancelBootstrap as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    const qc = new QueryClient();
    const { result } = renderHook(() => useCancelBootstrap('t1'), {
      wrapper: makeWrapper(qc),
    });
    await act(async () => {
      await result.current.mutateAsync();
    });
    expect(api.cancelBootstrap).toHaveBeenCalledWith('t1');
  });
});
