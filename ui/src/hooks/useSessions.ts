import { useQuery } from '@tanstack/react-query';

import { api, type Session } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';

// Session-event invalidation is centralized in useSessionEvents (mounted once
// at app root). This hook is a plain query — no per-component subscription.
export function useSessions(taskId: string | null) {
  return useQuery<Session[]>({
    queryKey: queryKeys.sessionsForTask(taskId),
    queryFn: () => (taskId ? api.listSessions(taskId) : Promise.resolve([])),
    enabled: !!taskId,
  });
}
