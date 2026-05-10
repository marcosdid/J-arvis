import type { QueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { dispatch } from '../lib/events';
import { queryKeys } from '../lib/query-keys';
import { connectWs } from '../lib/ws';

export function useSessionEvents(queryClient: QueryClient): void {
  useEffect(() => {
    const conn = connectWs((event) => {
      dispatch(event, {
        'session.status': () => {
          queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
          queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
        },
        'session.stopped': () => {
          queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
          queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
        },
        'task.created': () => {
          queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
        },
        'task.updated': () => {
          queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
        },
      });
    });
    return () => conn.disconnect();
  }, [queryClient]);
}
