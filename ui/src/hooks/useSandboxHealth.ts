import { useQuery } from '@tanstack/react-query';

import * as HealthBinding from '@/wailsjs/go/api/HealthAPI';

export type SandboxHealth = {
  sandbox_available: boolean;
  sandbox_reason: string;
};

// The Go probe is captured at boot (hook-server bind + ai-jail PATH check) and
// never re-evaluated, so a single fetch is enough — no refetch interval.
export function useSandboxHealth() {
  return useQuery<SandboxHealth>({
    queryKey: ['sandbox-health'],
    queryFn: async () => {
      const snap = await HealthBinding.Snapshot();
      return {
        sandbox_available: snap.sandbox_available ?? false,
        sandbox_reason: snap.sandbox_reason ?? '',
      };
    },
    staleTime: Infinity,
    retry: false,
  });
}
