import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, type Run } from '../lib/api';
import { queryKeys } from '../lib/query-keys';

/**
 * F6.i — query da run ativa pra uma task.
 *
 * Retorna `null` quando 404 (sem run ativa). React Query refetcha quando
 * useSessionEvents invalida `queryKeys.run(taskId)` (run.status/failed/stopped).
 */
export function useRun(taskId: string) {
  return useQuery<Run | null>({
    queryKey: queryKeys.run(taskId),
    queryFn: async () => {
      try {
        return await api.getActiveRun(taskId);
      } catch (err) {
        const msg = (err as Error).message ?? '';
        if (msg.startsWith('HTTP 404')) {
          return null;
        }
        throw err;
      }
    },
  });
}

export function useStartRun(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.startRun(taskId),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.run(taskId) }),
  });
}

export function useStopRun(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => api.stopRun(runId),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.run(taskId) }),
  });
}

export function useBootstrapManifest(taskId: string) {
  return useMutation({ mutationFn: () => api.bootstrapManifest(taskId) });
}
