import { useQuery } from '@tanstack/react-query';

export type SystemHealth = {
  cpu_pct: number;
  mem_used_bytes: number;
  mem_total_bytes: number;
  uptime_seconds: number;
  active_alerts_count: number;
};

async function fetchHealth(): Promise<SystemHealth> {
  const r = await fetch('/api/health');
  if (!r.ok) throw new Error(`health endpoint ${r.status}`);
  return r.json();
}

export function useSystemHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 5_000,
    staleTime: 4_000,
    retry: false,
  });
}
