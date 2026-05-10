import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { queryKeys } from '../lib/query-keys';

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: Parameters<typeof api.createTask>[0]) => api.createTask(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.tasks }),
  });
}

export function usePatchTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Parameters<typeof api.patchTask>[1] }) =>
      api.patchTask(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.tasks }),
  });
}

export function useStartTaskSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId }: { taskId: string }) => api.startTaskSession(taskId),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.tasks }),
  });
}
