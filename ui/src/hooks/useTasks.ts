import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { queryKeys } from '../lib/query-keys';

export function useTasks(projectIds: string[] | undefined) {
  const sortedIds = projectIds?.length
    ? [...projectIds].sort()
    : undefined;
  return useQuery({
    queryKey: sortedIds?.length
      ? queryKeys.tasksForProject(sortedIds.join(','))
      : queryKeys.tasks,
    queryFn: () => api.listTasks(sortedIds),
  });
}
