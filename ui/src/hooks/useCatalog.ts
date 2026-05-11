import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { queryKeys } from '../lib/query-keys';

export function useCatalog() {
  return useQuery({
    queryKey: queryKeys.catalog,
    queryFn: () => api.getCatalog(),
    staleTime: Infinity,
  });
}
