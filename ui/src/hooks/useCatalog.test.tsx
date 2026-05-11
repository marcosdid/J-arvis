import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useCatalog } from './useCatalog';
import { api, type Catalog } from '../lib/api';

describe('useCatalog', () => {
  let qc: QueryClient;

  beforeEach(() => {
    qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.restoreAllMocks();
  });

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );

  it('fetches catalog and caches it', async () => {
    const fake: Catalog = {
      version: '1',
      fallback_permission_profile: 'yolo',
      permission_profiles: [
        { name: 'yolo', description: 'Y', claude_args: ['--dangerously-skip-permissions'] },
      ],
      templates: [
        {
          name: 'frontend',
          description: 'F',
          default_permission_profile: 'yolo',
          branch_prefix: 'feat-ui/',
        },
      ],
    };
    const spy = vi.spyOn(api, 'getCatalog').mockResolvedValue(fake);

    const { result } = renderHook(() => useCatalog(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(fake);

    // staleTime: Infinity → second mount uses cache, no second fetch
    const { result: r2 } = renderHook(() => useCatalog(), { wrapper });
    await waitFor(() => expect(r2.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalledTimes(1);
  });
});
