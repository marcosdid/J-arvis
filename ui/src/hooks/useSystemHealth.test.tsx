import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSystemHealth } from './useSystemHealth';

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
};

describe('useSystemHealth', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({
        cpu_pct: 12.4,
        mem_used_bytes: 2147483648,
        mem_total_bytes: 34359738368,
        uptime_seconds: 16380,
        active_alerts_count: 1,
      }),
    })));
  });
  afterEach(() => vi.unstubAllGlobals());

  it('fetches health data', async () => {
    const { result } = renderHook(() => useSystemHealth(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.cpu_pct).toBe(12.4);
    expect(result.current.data?.active_alerts_count).toBe(1);
  });

  it('throws on non-OK response', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) })));
    const { result } = renderHook(() => useSystemHealth(), { wrapper });
    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect((result.current.error as Error).message).toContain('503');
  });
});
