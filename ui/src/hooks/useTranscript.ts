import { useQuery } from '@tanstack/react-query';

import { api, type TranscriptMessage } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';

// session.tool_use invalidation is centralized in useSessionEvents.
export function useTranscript(sessionId: string | null) {
  return useQuery<TranscriptMessage[]>({
    queryKey: queryKeys.transcript(sessionId),
    queryFn: () => (sessionId ? api.getTranscript(sessionId) : Promise.resolve([])),
    enabled: !!sessionId,
  });
}
