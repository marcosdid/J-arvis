import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { queryKeys } from '../lib/query-keys';
import { useTasks } from './useTasks';

vi.mock('../lib/api', () => ({
  api: { listTasks: vi.fn() },
}));

import { api } from '../lib/api';

function makeWrapper(qc: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe('useTasks', () => {
  beforeEach(() => {
    (api.listTasks as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  });

  afterEach(() => vi.clearAllMocks());

  it('uses queryKeys.tasks when projectIds is undefined', async () => {
    const qc = new QueryClient();
    const { result } = renderHook(() => useTasks(undefined), { wrapper: makeWrapper(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(qc.getQueryData(queryKeys.tasks)).toEqual([]);
    expect(api.listTasks).toHaveBeenCalledWith(undefined);
  });

  it('uses queryKeys.tasks when projectIds is empty array', async () => {
    const qc = new QueryClient();
    const { result } = renderHook(() => useTasks([]), { wrapper: makeWrapper(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(qc.getQueryData(queryKeys.tasks)).toEqual([]);
    expect(api.listTasks).toHaveBeenCalledWith(undefined);
  });

  it('uses queryKeys.tasksForProject and sorts ids when projectIds non-empty', async () => {
    const qc = new QueryClient();
    const { result } = renderHook(() => useTasks(['p2', 'p1']), {
      wrapper: makeWrapper(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(qc.getQueryData(queryKeys.tasksForProject('p1,p2'))).toEqual([]);
    expect(api.listTasks).toHaveBeenCalledWith(['p1', 'p2']);
  });
});
