import { useQuery } from '@tanstack/react-query';

export type SystemHealth = {
  cpu_pct: number;
  mem_used_bytes: number;
  mem_total_bytes: number;
  uptime_seconds: number;
  active_alerts_count: number;
};

async function fetchHealth(): Promise<SystemHealth> {
  // F10: legacy Python endpoint removed. Synthetic placeholder until the
  // Go side exposes a HealthAPI.SystemStats binding in a future phase.
  return {
    cpu_pct: 0,
    mem_used_bytes: 0,
    mem_total_bytes: 0,
    uptime_seconds: 0,
    active_alerts_count: 0,
  };
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
